"""Credit wallet: grants, charging, idempotency, refunds, concurrency (real PostgreSQL)."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import DuplicateOperationError, InsufficientCreditsError
from app.extensions import db
from app.models.credits import CreditTransaction, Wallet
from app.models.user import User
from app.services import credit_service
from tests.conftest import register


def _make_user(client, email="alice@example.com"):
    register(client, email)
    return db.session.execute(select(User).where(User.email == email)).scalar_one()


def test_registration_grants_exactly_1000_credits(app, client, ctx):
    u = _make_user(client)
    assert credit_service.get_balance(u.id) == 1000
    txs = db.session.execute(select(CreditTransaction).where(CreditTransaction.user_id == u.id)).scalars().all()
    assert [t.type for t in txs] == ["initial_grant"] and txs[0].amount == 1000 and txs[0].balance_after == 1000


def test_duplicate_initial_grant_blocked_by_database(app, client, ctx):
    u = _make_user(client)
    with pytest.raises(IntegrityError):
        db.session.add(CreditTransaction(user_id=u.id, type="initial_grant", operation="initial_grant", amount=1000,
                                         balance_after=2000, reference="dupe-ref"))
        db.session.commit()
    db.session.rollback()


def test_charge_reduces_balance_and_records_ledger(app, client, ctx):
    u = _make_user(client)
    tx = credit_service.charge(u.id, "job_match", idempotency_key="key-job-0001")
    assert tx.amount == -50 and tx.balance_after == 950 and tx.status == "charged"
    assert credit_service.get_balance(u.id) == 950


def test_insufficient_credits_never_negative(app, client, ctx):
    u = _make_user(client)
    credit_service.charge(u.id, "ats_analysis", cost=950)
    with pytest.raises(InsufficientCreditsError) as ei:
        credit_service.charge(u.id, "ats_analysis")
    assert ei.value.extra == {"required": 100, "balance": 50}
    assert credit_service.get_balance(u.id) == 50


def test_database_check_constraint_forbids_negative_balance(app, client, ctx):
    u = _make_user(client)
    with pytest.raises(IntegrityError):
        db.session.execute(text("UPDATE wallets SET balance = -1 WHERE user_id = :u"), {"u": u.id})
        db.session.commit()
    db.session.rollback()


def test_idempotency_key_prevents_double_charge(app, client, ctx):
    u = _make_user(client)
    credit_service.charge(u.id, "job_match", idempotency_key="same-key-123")
    with pytest.raises(DuplicateOperationError):
        credit_service.charge(u.id, "job_match", idempotency_key="same-key-123")
    assert credit_service.get_balance(u.id) == 950


def test_refund_restores_balance_exactly_once(app, client, ctx):
    u = _make_user(client)
    tx = credit_service.charge(u.id, "skill_gap")
    r1 = credit_service.refund(tx.id, "test")
    r2 = credit_service.refund(tx.id, "test again")
    assert r1.amount == 75 and r2.id == r1.id
    assert credit_service.get_balance(u.id) == 1000
    n = db.session.execute(select(func.count()).select_from(CreditTransaction)
                           .where(CreditTransaction.type == "refund")).scalar_one()
    assert n == 1


def test_billable_refunds_when_body_raises(app, client, ctx):
    u = _make_user(client)
    with pytest.raises(RuntimeError):
        with credit_service.billable(u.id, "ats_analysis"):
            raise RuntimeError("boom")
    assert credit_service.get_balance(u.id) == 1000
    types = [t.type for t in db.session.execute(select(CreditTransaction).where(
        CreditTransaction.user_id == u.id).order_by(CreditTransaction.id)).scalars()]
    assert types == ["initial_grant", "debit", "refund"]


def test_billable_keeps_charge_on_success(app, client, ctx):
    u = _make_user(client)
    with credit_service.billable(u.id, "chat_message"):
        pass
    assert credit_service.get_balance(u.id) == 990


def test_concurrent_charges_cannot_double_spend(app, client):
    with app.app_context():
        uid = _make_user(client).id

    def attempt(i):
        with app.app_context():
            try:
                credit_service.charge(uid, "ats_analysis", idempotency_key=f"concurrent-{i:04d}")
                return "ok"
            except InsufficientCreditsError:
                return "insufficient"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(25)))
    assert results.count("ok") == 10 and results.count("insufficient") == 15
    with app.app_context():
        assert credit_service.get_balance(uid) == 0
        spent = db.session.execute(select(func.coalesce(func.sum(-CreditTransaction.amount), 0)).where(
            CreditTransaction.user_id == uid, CreditTransaction.type == "debit")).scalar_one()
        assert spent == 1000


def test_concurrent_identical_idempotency_key_charges_once(app, client):
    with app.app_context():
        uid = _make_user(client).id

    def attempt(_):
        with app.app_context():
            try:
                credit_service.charge(uid, "job_match", idempotency_key="double-click-key")
                return "ok"
            except DuplicateOperationError:
                return "dup"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count("ok") == 1 and results.count("dup") == 7
    with app.app_context():
        assert credit_service.get_balance(uid) == 950


def test_concurrent_refunds_credit_back_once(app, client):
    with app.app_context():
        uid = _make_user(client).id
        tx_id = credit_service.charge(uid, "ats_analysis").id

    def attempt(_):
        with app.app_context():
            try:
                credit_service.refund(tx_id, "race")
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(attempt, range(8)))
    with app.app_context():
        assert credit_service.get_balance(uid) == 1000
        n = db.session.execute(select(func.count()).select_from(CreditTransaction).where(
            CreditTransaction.type == "refund")).scalar_one()
        assert n == 1


def test_unknown_operation_rejected(app, client, ctx):
    u = _make_user(client)
    with pytest.raises(ValueError):
        credit_service.charge(u.id, "does_not_exist")
