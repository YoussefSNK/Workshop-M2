# Architecture — PROJECT RESILIENCE-ALPHA — Équipe G<n>

## 1. Intention

Démontrer, sur un périmètre maîtrisé, qu'un SI de paiement fictif peut **détecter** une
anomalie de sécurité, **décider** d'une remédiation et **l'exécuter seul**, puis prouver
que le service métier est de nouveau utilisable — sans intervention humaine corrective.

## 2. Composants et rôles

| Composant | Rôle | Techno |
|-----------|------|--------|
| Frontend | Dashboard : état des services, transactions, incidents, avancement de la reprise | React + Tailwind |
| Payment API | Initie et traite une transaction fictive ; expose `/metrics` et `/health` | FastAPI |
| Auth | Authentifie, émet des JWT | FastAPI |
| PostgreSQL | Données métier fictives (comptes, transactions) | Postgres 16 |
| Gateway / WAF | Unique entrée publique de l'API ; filtre les requêtes malveillantes | nginx + ModSecurity (OWASP CRS) |
| Prometheus / Loki | Métriques + journaux centralisés | Prometheus, Loki, Promtail |
| Grafana | Supervision lisible par le jury | Grafana |
| Détecteur ML | Repère un comportement anormal à partir des métriques | Isolation Forest (scikit-learn) |
| Moteur de remédiation | Reçoit l'incident, décide, agit sur les conteneurs, vérifie le retour | Python + proxy socket Docker |
| Assistant RAG | Aide l'opérateur à comprendre / consulter les procédures (lecture seule) | Ollama (≤8B) + LangChain + Chroma |
| SOPS | Chiffre les secrets dans le dépôt | SOPS |

## 3. Flux

**Flux métier (nominal).** Utilisateur → Gateway/WAF → Payment API → (Auth pour le JWT) →
PostgreSQL. La transaction aboutit, la Payment API émet des métriques (latence, code HTTP, débit)
et des logs.

**Flux de reprise (le cœur).**
1. Prometheus collecte les métriques (scrape 5 s) ; Promtail pousse les logs vers Loki.
2. Le détecteur ML lit les métriques, compare au baseline « normal » appris, lève une anomalie.
3. Il notifie le moteur de remédiation (incident = service touché + type d'effet observé).
4. Le moteur applique l'action décidée (ex. rate-limit + redémarrage ciblé du service saturé).
5. Il **vérifie** : une transaction de contrôle doit repasser. Sinon il escalade l'action.
6. Le dashboard reflète chaque étape (avant / pendant / après).

## 4. Scénario d'incident

- **Attaque principale** : flood / épuisement de ressources sur la Payment API depuis le PC
  Attaquant → explosion de la latence et du taux d'erreur (effet observable et mesurable).
- **Réponse** : restauration de **disponibilité** (rate-limit, redémarrage ciblé, isolation).
- **Attaque secondaire (bonus)** : tentative d'injection SQL → bloquée par le WAF, tracée au SIEM.
  Ici la réponse n'est pas « redémarrer » mais « bloquer + alerter » : on distingue bien
  *disponibilité* et *compromission* (exigence explicite du sujet).

## 5. Décisions de sécurité structurantes

- Le moteur de remédiation a des droits élevés : on les **borne** via un proxy du socket Docker
  (lister/inspecter/redémarrer uniquement — pas de création d'image, de volume, de réseau).
- DB, secrets, Prometheus, remédiation : réseau `backnet` **interne**, jamais publiés.
- Seuls frontend, API (via gateway) et Grafana sont exposés sur le réseau du groupe.
- Secrets chiffrés (SOPS) ; aucun secret en clair dans l'archive de rendu.

## 6. Limites assumées (à dire au jury)

- Prototype 4 jours : pas une plateforme de paiement industrielle.
- Modèle ML entraîné sur un baseline court → sensible au bruit ; on documentera faux positifs/négatifs.
- Remédiation = un répertoire d'actions prédéfinies, pas une IA décisionnelle autonome générale.

## 7. Réseau

Point d'accès `RESILIENCE-G<n>`, PC Hôte en `192.168.137.1`. PC Attaquant distinct.
PC de délestage IA optionnel (héberge uniquement Ollama) si la RAM du Hôte est insuffisante.
