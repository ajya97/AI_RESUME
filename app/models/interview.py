from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.models.mixins import TimestampMixin


class InterviewSession(TimestampMixin, db.Model):
    __tablename__ = "interview_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="in_progress")  # in_progress | completed
    difficulty = db.Column(db.String(10), nullable=False, default="Mixed")
    focus_category = db.Column(db.String(30), nullable=False, default="all")
    target_role = db.Column(db.String(200), nullable=False, default="")
    job_description = db.Column(db.Text)
    questions = db.Column(JSONB, nullable=False, default=list)
    avg_score = db.Column(db.Float)
    completed_at = db.Column(db.DateTime(timezone=True))
    credit_tx_id = db.Column(db.Integer, db.ForeignKey("credit_transactions.id", ondelete="SET NULL"))

    answers = db.relationship("InterviewAnswer", back_populates="session", cascade="all, delete-orphan",
                              passive_deletes=True, order_by="InterviewAnswer.question_index")
    resume = db.relationship("Resume")


class InterviewAnswer(TimestampMixin, db.Model):
    __tablename__ = "interview_answers"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    question_index = db.Column(db.Integer, nullable=False)
    question = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False, default="General")
    answer = db.Column(db.Text, nullable=False, default="")
    skipped = db.Column(db.Boolean, nullable=False, default=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    evaluation = db.Column(JSONB, nullable=False, default=dict)
    credit_tx_id = db.Column(db.Integer, db.ForeignKey("credit_transactions.id", ondelete="SET NULL"))

    session = db.relationship("InterviewSession", back_populates="answers")

    __table_args__ = (
        # One answer per question: a question can never be evaluated (and charged) twice.
        db.UniqueConstraint("session_id", "question_index", name="uq_answer_session_question"),
    )
