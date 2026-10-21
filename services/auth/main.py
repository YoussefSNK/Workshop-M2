"""Service d'authentification — émet des JWT (HS256).

Données 100% fictives. On hache les mots de passe avec bcrypt (directement, sans passlib :
la combinaison passlib+bcrypt récente est une source classique de bugs de vérification).
Le même secret JWT_SECRET sert à signer ici et à vérifier dans la Payment API.
Piste de durcissement à mentionner au jury : passer en RS256 (clé privée ici, clé publique
seule côté API, pour que l'API ne puisse jamais forger de jeton).
"""
import os
import time
import jwt
import bcrypt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-change-me")
JWT_ALGO = "HS256"
TOKEN_TTL = 3600  # secondes

# Utilisateurs fictifs (en vrai : table en base). Mots de passe hachés au démarrage.
_RAW_USERS = {"alice": "alice-pw", "bob": "bob-pw"}
USERS = {u: bcrypt.hashpw(p.encode(), bcrypt.gensalt()) for u, p in _RAW_USERS.items()}

app = FastAPI(title="Auth — RESILIENCE-ALPHA")


class LoginIn(BaseModel):
    username: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login")
def login(body: LoginIn):
    hashed = USERS.get(body.username)
    ok = False
    if hashed:
        try:
            ok = bcrypt.checkpw(body.password.encode(), hashed)
        except Exception:
            ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    now = int(time.time())
    token = jwt.encode(
        {"sub": body.username, "iat": now, "exp": now + TOKEN_TTL},
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL}


Instrumentator().instrument(app).expose(app)  # /metrics pour Prometheus