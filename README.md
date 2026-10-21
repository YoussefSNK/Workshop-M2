# Workshop 2026 — PROJECT RESILIENCE-ALPHA — Équipe G<n>

SI de paiement fictif qui **encaisse une attaque et se répare tout seul** (zero-touch
recovery), observable de bout en bout. Démonstrateur de cyber-résilience.

> Remplacer `<n>` par le numéro d'équipe partout (dossier, noms de rendus).

---

## 1. Prérequis (PC Hôte)

Windows 10/11 + Docker Desktop (WSL2), ≥ 16 Go RAM, ≥ 50 Go SSD. Pour l'assistant RAG :
Ollama installé avec un modèle ≤ 8B (`ollama pull llama3.1:8b`), ou sur le 3ᵉ PC de délestage.

## 2. Démarrage

```bash
cp .env.example .env
# mettre de vraies valeurs :
#   openssl rand -hex 32   -> JWT_SECRET
#   (POSTGRES_PASSWORD, GRAFANA_PASSWORD au choix, cohérents avec DATABASE_URL)
make up        # ou : docker compose up -d --build
```

Attendre ~90 s que le détecteur ML ait appris son baseline, puis jouer la démo :

```bash
make demo      # ou : ./scripts/demo.sh
```

Le script montre : transaction OK **avant**, dégradation **pendant** l'attaque, incident
**détecté et résolu automatiquement** (avec le RTO), transaction OK **après**.

## 3. Accès

| Service | URL | Exposé au réseau du groupe |
|---|---|---|
| Dashboard (supervision) | http://192.168.137.1:3000 | Oui |
| Payment API (via WAF) | http://192.168.137.1:8000 | Oui — cible de l'attaque |
| Grafana | http://192.168.137.1:3001 | Oui (jury) |
| Assistant RAG | http://192.168.137.1:8100/ask?q=... | interne |
| Prometheus / Loki / DB / Vault | — | Non (réseau interne `backnet`) |

## 4. La boucle de reprise (cœur du sujet)

```
Transaction → métriques/logs → Prometheus/Loki → Détecteur ML (Isolation Forest)
   → incident → Moteur de remédiation → restart ciblé (via proxy Docker)
   → VÉRIFICATION (transaction de contrôle) → service rétabli
```

Aucune intervention humaine entre l'anomalie et le retour à la normale. Le `/health` de l'API
fait un vrai `SELECT` : un conteneur « up » mais dont la base ne répond pas est **unhealthy**,
donc un simple redémarrage ne compte pas comme preuve de reprise.

## 5. Les 5 piliers → où ils vivent

| Pilier | Dossier | Techno |
|---|---|---|
| Développement | `services/{payment-api,auth,frontend}` | FastAPI, React/Tailwind |
| Infrastructure | `docker-compose.yml`, `infra/ansible`, `observability/` | Compose, Ansible, Prometheus/Grafana/Loki |
| IA / Data | `services/{ml-detector,rag-assistant}` | Isolation Forest, Ollama+LangChain+Chroma |
| Cybersécurité | `services/gateway` (WAF CRS), `attack/`, `.sops.yaml`, `secrets/` | ModSecurity, SOPS |
| Gouvernance | `docs/` | EBIOS RM, PCA/PRA, NIS2/DORA |

## 6. Attaques (depuis le PC Attaquant)

```bash
python3 attack/flood.py --target http://192.168.137.1:8000 --duration 40 --concurrency 120
./attack/sqli.sh http://192.168.137.1:8000     # doit renvoyer 403 (bloqué par le WAF)
```

- **Flood** = atteinte à la **disponibilité** → réponse : restauration automatique.
- **Injection SQL** = tentative de **compromission** → réponse : blocage WAF + trace (pas un redémarrage).

## 7. Sécurité — points à défendre

- Le moteur de remédiation n'a **pas** accès au socket Docker en direct : il passe par
  `docker-socket-proxy` qui n'autorise que lister et **redémarrer** (ni exec, ni volumes, ni images).
- DB, secrets, Prometheus, remédiation : réseau interne, jamais publiés.
- Secrets chiffrés via SOPS ; aucun secret en clair dans l'archive.

## 8. Limites assumées (à dire au jury)

- Prototype 4 jours, pas une plateforme industrielle.
- Le ML apprend un baseline court → documenter faux positifs/négatifs.
- La remédiation couvre la disponibilité ; corruption/compromission = investigation, hors reprise auto.

## 9. Déploiement reproductible (Ansible)

```bash
cd infra/ansible && ansible-playbook deploy.yml      # install + up + attente santé
ansible-playbook reset.yml                           # remise à zéro (down -v)
```

## 10. Contributions (à remplir)

| Membre | Rôle principal | Contribution identifiable |
|--------|----------------|---------------------------|
|        |                |                           |

---

### Arborescence

```
services/      payment-api, auth, frontend, gateway, ml-detector, remediation-engine, rag-assistant
observability/ prometheus, loki, promtail, grafana (datasources + dashboard)
attack/        flood.py, sqli.sh
infra/ansible/ deploy.yml, reset.yml
docs/          architecture, ebios-risk-matrix, pca-pra, nis2-dora
secrets/       modèle + règle SOPS
scripts/       demo.sh
```
