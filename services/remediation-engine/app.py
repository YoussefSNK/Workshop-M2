"""Moteur de remédiation — reçoit un incident, agit sur Docker, vérifie la reprise.

Chaîne : /incident (depuis le détecteur ML) -> décision -> action sur le conteneur
-> VÉRIFICATION (le service répond-il à nouveau ?) -> enregistrement avec le RTO mesuré.

Sécurité : ce service ne parle JAMAIS au socket Docker directement. Il passe par le
proxy (docker-socket-proxy) qui n'autorise que lister et redémarrer des conteneurs.
Pas de création d'image, de volume ni de réseau : c'est le moindre privilège exigé par le sujet.
"""
import os
import time
import uuid
import datetime
import docker
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
from prometheus_fastapi_instrumentator import Instrumentator

DOCKER_HOST = os.environ.get("DOCKER_HOST", "tcp://docker-socket-proxy:2375")
VERIFY_URL = os.environ.get("VERIFY_URL", "http://payment-api:8000/health")
API_URL = os.environ.get("API_URL", "http://payment-api:8000")
AUTH_URL = os.environ.get("AUTH_URL", "http://auth:8000")
CONTROL_USER = os.environ.get("CONTROL_USER", "alice")
CONTROL_PASSWORD = os.environ.get("CONTROL_PASSWORD", "alice-pw")
# Aller-retour d'un centime : prouve la chaîne métier complète sans modifier les soldes.
CONTROL_LEGS = [("ACC-ALICE", "ACC-BOB"), ("ACC-BOB", "ACC-ALICE")]
CONTROL_AMOUNT = "0.01"
WATCHED = ["payment-api", "auth", "db", "gateway"]

client = docker.DockerClient(base_url=DOCKER_HOST)
app = FastAPI(title="Moteur de remédiation — RESILIENCE-ALPHA")
INCIDENTS: list[dict] = []


class Incident(BaseModel):
    service: str
    effect: str
    severity: str = "high"
    metric: str | None = None
    observed: Any | None = None
    timestamp: str | None = None


def _containers(service: str):
    return client.containers.list(
        all=True, filters={"label": f"com.docker.compose.service={service}"}
    )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def control_transaction() -> list[str] | None:
    """Transaction de contrôle réelle : login (auth) -> virement aller-retour (API + base).
    Renvoie les ids des transactions créées, ou None si une étape échoue."""
    r = requests.post(f"{AUTH_URL}/login", timeout=3,
                      json={"username": CONTROL_USER, "password": CONTROL_PASSWORD})
    if r.status_code != 200:
        return None
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    ids = []
    for src, dst in CONTROL_LEGS:
        r = requests.post(f"{API_URL}/transactions", headers=headers, timeout=3,
                          json={"from_account": src, "to_account": dst, "amount": CONTROL_AMOUNT})
        if r.status_code != 200:
            return None
        ids.append(r.json()["id"])
    return ids


def verify_recovery(timeout: int = 45) -> list[str] | None:
    """Le service est rétabli seulement s'il RÉPOND et TRAITE une transaction.
    Un conteneur "up" ne suffit pas, un /health OK non plus."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(VERIFY_URL, timeout=3).status_code == 200:
                ids = control_transaction()
                if ids:
                    return ids
        except Exception:
            pass
        time.sleep(2)
    return None


def decide_and_act(inc: Incident) -> dict:
    """Décision simple et traçable : pour une perte de disponibilité, on redémarre le
    service touché puis on vérifie. (On pourrait étendre : isolation réseau, scale, etc.)"""
    action = "restart"
    targets = _containers(inc.service)
    acted = []
    for c in targets:
        try:
            c.restart(timeout=5)
            acted.append(c.name)
        except Exception as e:
            acted.append(f"{c.name} (échec: {e})")
    return {"action": action, "containers": acted}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    """État des services pour le dashboard : conteneur up ? service répond ?"""
    out = []
    for svc in WATCHED:
        cs = _containers(svc)
        state = cs[0].status if cs else "absent"
        healthy = None
        if svc == "payment-api":
            try:
                healthy = requests.get(VERIFY_URL, timeout=2).status_code == 200
            except Exception:
                healthy = False
        out.append({"service": svc, "container": state, "healthy": healthy})
    return out


@app.get("/incidents")
def incidents():
    return list(reversed(INCIDENTS))


@app.post("/incident")
def handle_incident(inc: Incident):
    started = _now()
    record = {
        "id": f"INC-{uuid.uuid4().hex[:8]}",
        "received_at": started.isoformat(),
        "service": inc.service,
        "effect": inc.effect,
        "severity": inc.severity,
        "status": "in_progress",
    }
    INCIDENTS.append(record)

    result = decide_and_act(inc)
    control_ids = verify_recovery()
    recovered = control_ids is not None
    rto = (_now() - started).total_seconds()

    record.update({
        "action": result["action"],
        "containers": result["containers"],
        "status": "resolved" if recovered else "escalate",
        "recovered": recovered,
        "control_transactions": control_ids or [],
        "rto_seconds": round(rto, 1),
    })
    print(f"[remediation] {record['id']} {record['status']} RTO={record['rto_seconds']}s", flush=True)
    return record


Instrumentator().instrument(app).expose(app)
