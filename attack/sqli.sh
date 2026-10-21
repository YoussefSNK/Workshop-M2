#!/usr/bin/env bash
# Attaque secondaire — tentative d'injection SQL, DOIT être bloquée par le WAF (403).
# Montre qu'on distingue DISPONIBILITÉ (flood) et COMPROMISSION (injection) :
# ici la bonne réponse n'est pas de redémarrer mais de BLOQUER + tracer.
# Usage : ./sqli.sh http://192.168.137.1:8000
set -euo pipefail
TARGET="${1:-http://192.168.137.1:8000}"
PAYLOAD="1' OR '1'='1"

echo "[sqli] Envoi d'une charge d'injection vers ${TARGET}/accounts ..."
CODE=$(curl -s -o /dev/null -w "%{http_code}" -G "${TARGET}/accounts" --data-urlencode "id=${PAYLOAD}")
echo "[sqli] Code HTTP renvoyé : ${CODE}"
if [ "${CODE}" = "403" ]; then
  echo "[sqli] OK : le WAF a bloqué l'injection (403). Événement à retrouver dans les logs."
else
  echo "[sqli] Attention : non bloqué (${CODE}). Vérifier MODSEC_RULE_ENGINE=On et le niveau PARANOIA."
fi
