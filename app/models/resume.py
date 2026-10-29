from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.models.mixins import TimestampMixin

REPORT_TYPES = ("ats", "job_match", "skill_gap")


class Resume(TimestampMixin, db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(80), nullable=False, unique=True)  # uuid.pdf, never user-controlled
    file_size = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    page_count = db.Column(db.Integer, nullable=False, default=1)
    parsed = db.Column(JSONB, nullable=False, default=dict)      # parse_resume() output minus raw_text
    raw_text = db.Column(db.Text, nullable=False, default="")
    # Structured, user-editable content used by the template library.
    content = db.Column(JSONB, nullable=False, default=dict)
    template_key = db.Column(db.String(30), nullable=False, default="classic", server_default="classic")

    user = db.relationship("User", backref=db.backref("resumes", lazy="dynamic", cascade="all, delete-orphan",
                                                      passive_deletes=True))
    reports = db.relationship("Report", back_populates="resume", cascade="all, delete-orphan",
                              passive_deletes=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "sha256", name="uq_resumes_user_sha"),
    )


class Report(TimestampMixin, db.Model):
    """ATS analyses, job-match reports and skill-gap reports."""

    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False, default="")
    score = db.Column(db.Integer)                    # ATS score / match % / coverage %
    status = db.Column(db.String(20), nullable=False, default="completed")
    inputs = db.Column(JSONB, nullable=False, default=dict)   # e.g. job description, target role
    data = db.Column(JSONB, nullable=False, default=dict)     # full result payload
    credit_tx_id = db.Column(db.Integer, db.ForeignKey("credit_transactions.id", ondelete="SET NULL"))

    resume = db.relationship("Resume", back_populates="reports")

    __table_args__ = (
        db.CheckConstraint("type in ('ats','job_match','skill_gap')", name="ck_reports_type"),
        db.Index("ix_reports_user_type_created", "user_id", "type", "created_at"),
    )
