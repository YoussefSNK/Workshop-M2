"""Couche base de données (SQLAlchemy 2.0) + modèles métier fictifs."""
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://payments_app:change_me@db:5432/payments"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    from_account: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    to_account: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def init_db():
    """Crée les tables et sème des comptes fictifs si la base est vide."""
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if s.query(Account).count() == 0:
            s.add_all([
                Account(id="ACC-ALICE", owner="Alice", balance=1000),
                Account(id="ACC-BOB", owner="Bob", balance=500),
                Account(id="ACC-MERCHANT", owner="Marchand", balance=0),
            ])
            s.commit()
