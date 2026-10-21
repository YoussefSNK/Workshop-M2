#!/usr/bin/env bash
# Démonstration de bout en bout de la boucle de reprise autonome :
# AVANT -> ATTAQUE -> (détection ML) -> (remédiation auto) -> APRÈS, avec le RTO mesuré.
#
# Prérequis : la plateforme tourne et est "healthy" (docker compose up -d --build,
# puis attendre ~90s que le détecteur ML ait appris son baseline).
#
# Usage : ./scripts/demo.sh
set -uo pipefail

FRONT="${FRONT:-http://localhost:3000}"     # entrée applicative (dashboard + proxys)
ATTACK="${ATTACK:-http://localhost:8000}"   # entrée API publique (cible de l'attaque)
HERE="$(cd "$(dirname "$0")/.." && pwd)"

say() { printf "\n\033[1m== %s ==\033[0m\n" "$1"; }

token() {
  curl -s -X POST "$FRONT/auth/login" -H 'Content-Type: application/json' \
    -d '{"username":"alice","password":"alice-pw"}' \
  | python3 -c "import sys,json
try:
    print(json.load(sys.stdin).get('access_token',''))
except Exception:
    print('')"
}

transaction() {
  local t; t="$(token)"
  if [ -z "$t" ]; then echo "login KO (pas de jeton) — auth indisponible ?"; return; fi
  curl -s -o /dev/null -w "%{http_code} en %{time_total}s" \
    -X POST "$FRONT/api/transactions" \
    -H "Authorization: Bearer $t" -H 'Content-Type: application/json' \
    -d '{"from_account":"ACC-ALICE","to_account":"ACC-BOB","amount":5}'
}

say "Attente que le service réponde"
for _ in $(seq 1 60); do
  curl -sf "$ATTACK/health" >/dev/null 2>&1 && break
  sleep 2
done

say "AVANT — transaction de contrôle"
echo "Résultat : $(transaction)"

# On note les incidents DÉJÀ présents (runs précédents) pour ne compter que les NOUVEAUX.
PRE_IDS="$(curl -s "$FRONT/remediation/incidents" \
  | python3 -c "import sys,json
try: print(' '.join(i['id'] for i in json.load(sys.stdin)))
except Exception: print('')" 2>/dev/null)"

say "ATTAQUE — flood sur la Payment API (40s)"
python3 "$HERE/attack/flood.py" --target "$ATTACK" --duration 40 --concurrency 120 &
FLOOD_PID=$!

sleep 12
say "PENDANT — transaction sous charge (doit se dégrader)"
echo "Résultat : $(transaction)"

say "DÉTECTION + REMÉDIATION — attente d'un incident NOUVEAU résolu automatiquement"
RESOLVED=""
for _ in $(seq 1 60); do
  RESOLVED="$(curl -s "$FRONT/remediation/incidents" \
    | PRE="$PRE_IDS" python3 -c "import sys,json,os
pre=set(os.environ.get('PRE','').split())
d=json.load(sys.stdin)
r=[i for i in d if i.get('status')=='resolved' and i['id'] not in pre]
print(f\"{r[0]['id']} RTO={r[0]['rto_seconds']}s\" if r else '')" 2>/dev/null)"
  [ -n "$RESOLVED" ] && break
  sleep 3
done
wait "$FLOOD_PID" 2>/dev/null
if [ -n "$RESOLVED" ]; then echo "Incident de CE run traité automatiquement : $RESOLVED"
else echo "Aucun NOUVEAU incident résolu sur ce run (détection pas re-déclenchée — voir note ci-dessous)."; fi

say "APRÈS — transaction de contrôle (doit repasser)"
sleep 3
echo "Résultat : $(transaction)"
say "Fin. Ouvrir le dashboard ($FRONT) et Grafana (http://localhost:3001) pour les courbes."