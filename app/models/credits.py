from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow


class Wallet(db.Model):
    """One credit wallet per user. ``balance`` is only ever changed by
    app.services.credit_service while holding a row lock (SELECT ... FOR UPDATE)."""

    __tablename__ = "wallets"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="wallet")

    __table_args__ = (
        db.CheckConstraint("balance >= 0", name="ck_wallets_balance_nonnegative"),
    )


class CreditTransaction(TimestampMixin, db.Model):
    """Append-only ledger. ``amount`` is signed (debits negative)."""

    __tablename__ = "credit_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # initial_grant | debit | refund | adjustment
    type = db.Column(db.String(20), nullable=False)
    operation = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    # Server-generated unique reference for every ledger row (audit trail).
    reference = db.Column(db.String(64), nullable=False, unique=True)
    # Optional client-supplied key; (user_id, idempotency_key) is unique so a
    # double-submitted request can never be charged twice.
    idempotency_key = db.Column(db.String(80))
    # For refunds: the debit being refunded (unique -> at most ONE refund each).
    refund_of_id = db.Column(db.Integer, db.ForeignKey("credit_transactions.id", ondelete="SET NULL"), unique=True)
    # For debits: charged | refunded
    status = db.Column(db.String(12), nullable=False, default="posted")
    description = db.Column(db.String(255), nullable=False, default="")
    meta = db.Column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        db.CheckConstraint("type in ('initial_grant','debit','refund','adjustment')", name="ck_credit_tx_type"),
        # Exactly one initial grant per user, enforced by the database.
        db.Index("uq_credit_tx_one_initial_grant", "user_id", unique=True,
                 postgresql_where=db.text("type = 'initial_grant'")),
        db.Index("uq_credit_tx_user_idempotency", "user_id", "idempotency_key", unique=True,
                 postgresql_where=db.text("idempotency_key IS NOT NULL")),
    )


class AIUsage(TimestampMixin, db.Model):
    """Provider token usage + estimated provider cost.

    Deliberately separate from application credits: credits are a flat price
    list, whereas this records what the model provider actually reported."""

    __tablename__ = "ai_usage"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    operation = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(120), nullable=False, default="")
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    estimated_cost_usd = db.Column(db.Numeric(12, 6))  # NULL when no price configured
    credit_tx_id = db.Column(db.Integer, db.ForeignKey("credit_transactions.id", ondelete="SET NULL"))
