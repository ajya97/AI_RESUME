from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow

THEMES = ("dark", "light")


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # Stored lower-cased; uniqueness enforced by the database.
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False, default="")
    theme = db.Column(db.String(10), nullable=False, default="dark", server_default="dark")
    is_active_account = db.Column("is_active", db.Boolean, nullable=False, default=True, server_default=db.true())
    last_login_at = db.Column(db.DateTime(timezone=True))
    password_changed_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    wallet = db.relationship("Wallet", back_populates="user", uselist=False,
                             cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint("theme in ('dark','light')", name="ck_users_theme"),
    )

    # Flask-Login uses `is_active`; map it to our column.
    @property
    def is_active(self):  # type: ignore[override]
        return bool(self.is_active_account)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = utcnow()

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return str(self.id)

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]

    @property
    def initials(self) -> str:
        parts = (self.full_name or self.email).replace("@", " ").split()
        return "".join(p[0] for p in parts[:2]).upper() or "U"
