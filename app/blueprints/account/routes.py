"""Account: profile, settings, theme preference, credits."""

import shutil
from pathlib import Path

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from app.blueprints.account import account_bp
from app.blueprints.auth.routes import validate_password
from app.core.exceptions import ValidationError
from app.core.http import json_body, page_args
from app.extensions import db
from app.models.user import THEMES, User
from app.services import credit_service
from app.services.credit_service import OPERATION_LABELS


@account_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = (request.form.get("full_name") or "").strip()
        if not name or len(name) > 120:
            flash("Please enter a valid name (max 120 characters).", "error")
        else:
            current_user.full_name = name
            db.session.commit()
            flash("Profile updated.", "success")
        return redirect(url_for("account.profile"))
    return render_template("dashboard/profile.html")


@account_bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    cur, new = request.form.get("current_password") or "", request.form.get("new_password") or ""
    if not current_user.check_password(cur):
        flash("Current password is incorrect.", "error")
    elif new != (request.form.get("confirm_password") or ""):
        flash("New passwords do not match.", "error")
    elif (err := validate_password(new, current_user.email)):
        flash(err, "error")
    else:
        current_user.set_password(new)
        db.session.commit()
        flash("Password changed.", "success")
    return redirect(url_for("account.profile"))


@account_bp.route("/settings")
@login_required
def settings():
    return render_template("dashboard/settings.html")


@account_bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    if not current_user.check_password(request.form.get("password") or ""):
        flash("Password is incorrect. Account not deleted.", "error")
        return redirect(url_for("account.settings"))
    uid = current_user.id
    user = db.session.get(User, uid)
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / str(uid)
    logout_user()
    session.clear()
    db.session.delete(user)  # cascades to every owned row
    db.session.commit()
    shutil.rmtree(folder, ignore_errors=True)
    flash("Your account and all stored data were deleted.", "info")
    return redirect(url_for("pages.index"))


@account_bp.route("/credits")
@login_required
def credits_page():
    return render_template("dashboard/credits.html", labels=OPERATION_LABELS)


@account_bp.route("/api/settings/theme", methods=["POST"])
@login_required
def set_theme():
    theme = json_body().get("theme")
    if theme not in THEMES:
        raise ValidationError("Theme must be 'dark' or 'light'.")
    current_user.theme = theme
    db.session.commit()
    return jsonify({"success": True, "theme": theme})


@account_bp.route("/api/credits")
@login_required
def credits_api():
    """GET /api/credits?page=&per_page= — balance, price list and the user's ledger."""
    page, per = page_args(15, 50)
    txs = credit_service.recent_transactions(current_user.id, per, (page - 1) * per)
    return jsonify({
        "balance": credit_service.get_balance(current_user.id),
        "costs": current_app.config["CREDIT_COSTS"],
        "labels": OPERATION_LABELS,
        "transactions": [{
            "id": t.id, "type": t.type, "operation": t.operation,
            "label": OPERATION_LABELS.get(t.operation, t.operation), "amount": t.amount,
            "balance_after": t.balance_after, "status": t.status, "description": t.description,
            "reference": t.reference, "created_at": t.created_at.isoformat(),
        } for t in txs],
        "page": page, "per_page": per,
    })
