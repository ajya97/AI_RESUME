from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow


class ChatSession(TimestampMixin, db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False, default="New chat")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    messages = db.relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan",
                               passive_deletes=True, order_by="ChatMessage.id")
    resume = db.relationship("Resume")


class ChatMessage(TimestampMixin, db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    credit_tx_id = db.Column(db.Integer, db.ForeignKey("credit_transactions.id", ondelete="SET NULL"))

    session = db.relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        db.CheckConstraint("role in ('user','assistant')", name="ck_chat_role"),
    )
