"""Détecteur d'anomalies — Isolation Forest sur les métriques Prometheus.

Principe (défendable devant le jury) :
1. Au démarrage, on observe le service en fonctionnement NORMAL pendant BASELINE_SECONDS
   et on collecte des vecteurs de features (débit, taux d'erreur, latence p95).
2. On entraîne un Isolation Forest : un modèle NON supervisé qui apprend la forme du
   "normal" sans qu'on lui code de seuil en dur. Il isole ensuite les points atypiques.
3. En continu, on score chaque nouveau vecteur. Si le modèle le juge anormal
   CONSECUTIVE_ANOMALIES fois de suite (anti faux positif), on envoie un incident au
   moteur de remédiation.

Ce composant ne corrige rien lui-même : il détecte et alerte. La correction est le rôle
du moteur de remédiation (séparation voulue : détection ≠ action).
"""
import os
import time
import datetime
import requests
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib

PROM = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
REMEDIATION_URL = os.environ.get("REMEDIATION_URL", "http://remediation-engine:9000/incident")
BASELINE_SECONDS = int(os.environ.get("BASELINE_SECONDS", "60"))
CONSECUTIVE = int(os.environ.get("CONSECUTIVE_ANOMALIES", "3"))
SAMPLE_EVERY = 5
MODEL_PATH = "/models/iforest.joblib"

QUERIES = {
    "rate": 'sum(rate(http_requests_total{job="payment-api"}[1m]))',
    "errors": 'sum(rate(http_requests_total{job="payment-api",status=~"5.."}[1m]))',
    "p95": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{job="payment-api"}[1m])) by (le))',
}


def query(expr: str) -> float:
    """Requête instantanée Prometheus → une valeur (0.0 si vide/NaN)."""
    try:
        r = requests.get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=5)
        result = r.json().get("data", {}).get("result", [])
        if not result:
            return 0.0
        v = float(result[0]["value"][1])
        return 0.0 if np.isnan(v) else v
    except Exception:
        return 0.0


def features() -> list[float]:
    rate = query(QUERIES["rate"])
    errors = query(QUERIES["errors"])
    p95 = query(QUERIES["p95"])
    err_ratio = errors / rate if rate > 0 else 0.0
    return [rate, err_ratio, p95]


def wait_for_prometheus():
    for _ in range(60):
        try:
            if requests.get(f"{PROM}/-/ready", timeout=3).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)


def collect_baseline() -> np.ndarray:
    print(f"[ml] Apprentissage du baseline pendant {BASELINE_SECONDS}s...", flush=True)
    samples = []
    n = max(4, BASELINE_SECONDS // SAMPLE_EVERY)
    for _ in range(n):
        samples.append(features())
        time.sleep(SAMPLE_EVERY)
    arr = np.array(samples, dtype=float)
    # un peu de bruit pour éviter un baseline dégénéré si le trafic est très stable
    arr += np.random.normal(0, 1e-6, arr.shape)
    return arr


def send_incident(vec, score):
    payload = {
        "service": "payment-api",
        "effect": "latency_spike" if vec[2] > 1 else "error_spike",
        "severity": "high",
        "metric": "http_request_duration_seconds / error_ratio",
        "observed": {"rate": vec[0], "error_ratio": vec[1], "p95": vec[2], "score": score},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        requests.post(REMEDIATION_URL, json=payload, timeout=5)
        print(f"[ml] INCIDENT envoyé : {payload['effect']} (score={score:.3f})", flush=True)
    except Exception as e:
        print(f"[ml] Échec envoi incident : {e}", flush=True)


def main():
    wait_for_prometheus()
    baseline = collect_baseline()
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(baseline)
    joblib.dump(model, MODEL_PATH)
    print("[ml] Modèle entraîné. Surveillance en cours.", flush=True)

    streak = 0
    cooldown = 0
    while True:
        time.sleep(SAMPLE_EVERY)
        if cooldown > 0:
            cooldown -= 1
            continue
        vec = features()
        pred = model.predict([vec])[0]          # -1 = anomalie, 1 = normal
        score = float(model.score_samples([vec])[0])
        if pred == -1:
            streak += 1
            print(f"[ml] anomalie potentielle {streak}/{CONSECUTIVE} {vec}", flush=True)
            if streak >= CONSECUTIVE:
                send_incident(vec, score)
                streak = 0
                cooldown = 12               # ~60s de pause, le temps que la remédiation agisse
        else:
            streak = 0


if __name__ == "__main__":
    main()
