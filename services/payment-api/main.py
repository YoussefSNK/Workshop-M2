"""Payment API — cœur métier fictif.

Expose : /health (vérifie vraiment la base), /metrics (Prometheus),
et les opérations de paiement protégées par JWT.
Le /health fait un vrai SELECT : si la base est KO, l'API est "unhealthy"
même si le conteneur tourne -> un redémarrage seul ne suffit pas à prouver la reprise.
"""
import os
import uuid
import jwt
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from prometheus_fastapi_instrumentator import Instrumentator

from db import SessionLocal, Account, Transaction, init_db, engine

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-change-me")
JWT_ALGO = "HS256"

app = FastAPI(title="Payment API — RESILIENCE-ALPHA")


@app.on_event("startup")
def _startup():
    init_db()


def require_user(authorization: str = Header(default="")) -> str:
    """Dépendance d'auth : vérifie le JWT émis par le service auth."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Jeton manquant")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Jeton invalide")
    return payload["sub"]


class TransferIn(BaseModel):
    from_account: str
    to_account: str
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("Le montant doit être positif")
        return v


@app.get("/health")
def health():
    # Vraie vérification de dépendance : la base répond-elle ?
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Base indisponible")


@app.get("/accounts")
def list_accounts(_user: str = Depends(require_user)):
    with SessionLocal() as s:
        return [
            {"id": a.id, "owner": a.owner, "balance": float(a.balance)}
            for a in s.query(Account).all()
        ]


@app.post("/transactions")
def create_transaction(body: TransferIn, user: str = Depends(require_user)):
    with SessionLocal() as s:
        src = s.get(Account, body.from_account)
        dst = s.get(Account, body.to_account)
        if not src or not dst:
            raise HTTPException(status_code=404, detail="Compte inconnu")
        if Decimal(str(src.balance)) < body.amount:
            raise HTTPException(status_code=422, detail="Solde insuffisant")
        src.balance = Decimal(str(src.balance)) - body.amount
        dst.balance = Decimal(str(dst.balance)) + body.amount
        tx = Transaction(
            id=f"TX-{uuid.uuid4().hex[:10]}",
            from_account=body.from_account,
            to_account=body.to_account,
            amount=body.amount,
            status="completed",
        )
        s.add(tx)
        s.commit()
        return {"id": tx.id, "status": tx.status, "by": user}


@app.get("/transactions")
def list_transactions(_user: str = Depends(require_user)):
    with SessionLocal() as s:
        rows = s.query(Transaction).order_by(Transaction.created_at.desc()).limit(50)
        return [
            {
                "id": t.id, "from": t.from_account, "to": t.to_account,
                "amount": float(t.amount), "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ]


Instrumentator().instrument(app).expose(app)  # /metrics : latence, codes HTTP, débit
