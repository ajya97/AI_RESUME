"""
Credit wallet service — the ONLY code that changes a wallet balance.

Charging policy (reserve-then-refund)
-------------------------------------
1. Before any AI work the server debits the operation's price in its own
   committed transaction. The wallet row is locked with ``SELECT ... FOR UPDATE``
   so concurrent requests are serialised per user and the same credits can
   never be spent twice; a CHECK constraint additionally forbids negative
   balances.
2. If the operation then fails for ANY reason (provider error, unparsable AI
   output, database error while saving the result) the debit is refunded.
3. A refund is unique per debit (``refund_of_id`` UNIQUE) so a debit can never
   be refunded twice.
4. Browser-supplied costs/balances are never used; prices come from
   ``CREDIT_COSTS`` in server configuration.

Idempotency: callers may pass a client-generated ``Idempotency-Key``; the
database rejects a second debit with the same (user, key), so a double-clicked
button is charged once and the duplicate gets HTTP 409.
"""

import uuid
from contextlib import contextmanager

from flask import current_app, g
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DuplicateOperationError, InsufficientCreditsError
from app.extensions import db
from app.models.credits import AIUsage, CreditTransaction, Wallet

OPERATION_LABELS = {
    "initial_grant": "Welcome credits",
    "ats_analysis": "ATS resume analysis",
    "job_match": "Job match analysis",
    "skill_gap": "Skill-gap analysis",
    "interview_session": "Interview session (question generation)",
    "interview_evaluation": "Interview answer evaluation",
    "chat_message": "Resume chatbot message",
}


# ─── helpers ──────────────────────────────────────────────────────────────
def _ref() -> str:
    return uuid.uuid4().hex


def cost_of(operation: str) -> int:
    try:
        return int(current_app.config["CREDIT_COSTS"][operation])
    except KeyError:
        raise ValueError(f"Unknown billable operation: {operation}")


def _lock_wallet(user_id: int) -> Wallet:
    wallet = db.session.execute(
        select(Wallet).where(Wallet.user_id == user_id)
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if wallet is None:
        raise LookupError(f"No wallet for user {user_id}")
    return wallet


# ─── public API ───────────────────────────────────────────────────────────
def grant_initial_credits(user) -> CreditTransaction:
    """Create the wallet and the one-and-only welcome grant for a NEW user.

    Must be called inside the registration transaction (does not commit).
    Duplicate grants are impossible: partial unique index on
    (user_id) WHERE type = 'initial_grant' and wallet PK on user_id."""
    amount = int(current_app.config["INITIAL_USER_CREDITS"])
    wallet = Wallet(user_id=user.id, balance=amount)
    tx = CreditTransaction(
        user_id=user.id, type="initial_grant", operation="initial_grant", amount=amount,
        balance_after=amount, reference=_ref(), status="posted",
        description="Welcome credits on registration",
    )
    db.session.add_all([wallet, tx])
    return tx


def get_balance(user_id: int) -> int:
    value = db.session.execute(select(Wallet.balance).where(Wallet.user_id == user_id)).scalar_one_or_none()
    return int(value or 0)


def charge(user_id: int, operation: str, *, cost: int | None = None,
           idempotency_key: str | None = None, description: str = "",
           meta: dict | None = None) -> CreditTransaction:
    """Atomically debit credits and commit. Raises InsufficientCreditsError /
    DuplicateOperationError without changing the balance."""
    amount = int(cost if cost is not None else cost_of(operation))
    if amount <= 0:
        raise ValueError("Charge amount must be positive")

    wallet = _lock_wallet(user_id)  # row lock held until commit/rollback
    try:
        if idempotency_key:
            dup = db.session.execute(
                select(CreditTransaction.id).where(
                    CreditTransaction.user_id == user_id,
                    CreditTransaction.idempotency_key == idempotency_key)
            ).first()
            if dup:
                db.session.rollback()
                raise DuplicateOperationError(
                    "This request was already submitted. Please wait for it to finish.")
        if wallet.balance < amount:
            balance = wallet.balance
            db.session.rollback()
            raise InsufficientCreditsError(
                f"Not enough credits: this action costs {amount} but you have {balance}.",
                required=amount, balance=balance)
        wallet.balance -= amount
        tx = CreditTransaction(
            user_id=user_id, type="debit", operation=operation, amount=-amount,
            balance_after=wallet.balance, reference=_ref(), idempotency_key=idempotency_key,
            status="charged", description=description or OPERATION_LABELS.get(operation, operation),
            meta=meta or {},
        )
        db.session.add(tx)
        db.session.commit()
        return tx
    except IntegrityError:
        db.session.rollback()
        raise DuplicateOperationError("This request was already submitted. Please wait for it to finish.")


def refund(debit_tx_id: int, reason: str = "") -> CreditTransaction | None:
    """Refund a debit exactly once. Safe to call repeatedly (idempotent)."""
    debit = db.session.get(CreditTransaction, debit_tx_id)
    if debit is None or debit.type != "debit":
        raise ValueError("Only debit transactions can be refunded")
    wallet = _lock_wallet(debit.user_id)  # lock order: wallet first, then ledger row
    debit = db.session.execute(
        select(CreditTransaction).where(CreditTransaction.id == debit_tx_id)
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one()
    if debit.status == "refunded":
        db.session.rollback()
        return db.session.execute(
            select(CreditTransaction).where(CreditTransaction.refund_of_id == debit_tx_id)).scalar_one_or_none()
    try:
        amount = -debit.amount
        wallet.balance += amount
        debit.status = "refunded"
        tx = CreditTransaction(
            user_id=debit.user_id, type="refund", operation=debit.operation, amount=amount,
            balance_after=wallet.balance, reference=_ref(), refund_of_id=debit.id, status="posted",
            description=f"Refund: {OPERATION_LABELS.get(debit.operation, debit.operation)}",
            meta={"reason": reason[:200], "debit_reference": debit.reference},
        )
        db.session.add(tx)
        db.session.commit()
        return tx
    except IntegrityError:
        db.session.rollback()
        return None  # someone else already refunded it


@contextmanager
def billable(user_id: int, operation: str, *, idempotency_key: str | None = None,
             description: str = "", cost: int | None = None):
    """Debit up-front, refund automatically if the body raises.

    Usage::

        with billable(user.id, "job_match", idempotency_key=key) as tx:
            result = do_ai_work()
            db.session.add(Report(..., credit_tx_id=tx.id))
            db.session.commit()
    """
    tx = charge(user_id, operation, cost=cost, idempotency_key=idempotency_key, description=description)
    tx_id = tx.id
    g.ai_usage = []
    try:
        yield tx
    except BaseException as exc:
        db.session.rollback()
        try:
            refund(tx_id, reason=f"{operation} failed: {type(exc).__name__}")
        except Exception:  # pragma: no cover - last-resort logging
            current_app.logger.exception("CRITICAL: refund failed for credit tx %s", tx_id)
        raise
    finally:
        _persist_usage(user_id, operation, tx_id)


def _persist_usage(user_id: int, operation: str, tx_id: int) -> None:
    """Store provider-reported token usage (separate from application credits)."""
    items = getattr(g, "ai_usage", None) or []
    g.ai_usage = []
    if not items:
        return
    try:
        in_price = current_app.config.get("MODEL_INPUT_PRICE_PER_1M")
        out_price = current_app.config.get("MODEL_OUTPUT_PRICE_PER_1M")
        for it in items:
            cost = None
            if in_price is not None and out_price is not None:
                cost = (it["input_tokens"] * in_price + it["output_tokens"] * out_price) / 1_000_000
            db.session.add(AIUsage(
                user_id=user_id, operation=operation, model=it.get("model", ""),
                input_tokens=it["input_tokens"], output_tokens=it["output_tokens"],
                estimated_cost_usd=cost, credit_tx_id=tx_id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Could not persist AI usage")


def recent_transactions(user_id: int, limit: int = 50, offset: int = 0):
    return db.session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.id.desc()).limit(limit).offset(offset)
    ).scalars().all()


def usage_by_operation(user_id: int) -> list[dict]:
    """Net credits spent per operation (debits minus refunds)."""
    rows = db.session.execute(
        select(CreditTransaction.operation, func.sum(-CreditTransaction.amount))
        .where(CreditTransaction.user_id == user_id,
               CreditTransaction.type.in_(("debit", "refund")))
        .group_by(CreditTransaction.operation)
    ).all()
    return [{"operation": op, "label": OPERATION_LABELS.get(op, op), "credits": int(total or 0)}
            for op, total in rows if (total or 0) > 0]
