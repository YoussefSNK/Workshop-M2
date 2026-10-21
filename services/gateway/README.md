# Gateway / WAF

Pas de Dockerfile : on utilise l'image officielle `owasp/modsecurity-crs:4.25.2-nginx-alpine-lts`
(ModSecurity + règles OWASP Core Rule Set). Configurée en reverse-proxy dans docker-compose.yml :
- `BACKEND=http://payment-api:8000` : le WAF relaie vers l'API.
- `MODSEC_RULE_ENGINE=On` : blocage actif. Mettre `DetectionOnly` pour observer sans bloquer.
- `PARANOIA=1` : niveau de sévérité des règles.

Rôle dans la démo :
- bloque la tentative d'injection SQL (attaque secondaire) et la journalise → visible au SIEM.
- laisse passer le trafic légitime ; le flood (attaque principale) sature l'API malgré le WAF,
  c'est la remédiation qui restaure la disponibilité.

Règles maison : monter un fichier dans /etc/modsecurity.d/ si besoin d'ajouter des règles.
