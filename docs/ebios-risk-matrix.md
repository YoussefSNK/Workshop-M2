# Analyse de risques EBIOS RM (départ) — PROJECT RESILIENCE-ALPHA — G<n>

> Version de lundi, à affiner. EBIOS RM se lit en 5 ateliers ; voici l'ossature + une matrice exploitable.

## Atelier 1 — Cadrage & valeurs métier

| Valeur métier | Bien support | Événement redouté | Impact |
|---------------|--------------|-------------------|--------|
| Traiter un paiement | Payment API, DB | Indisponibilité du service de paiement | Opérations partenaires bloquées, perte de confiance |
| Intégrité des transactions | DB, Auth | Transaction falsifiée / rejouée | Fraude, perte financière fictive |
| Confidentialité des données | DB, secrets | Exfiltration de données fictives | Atteinte réputation, sanction (NIS2/DORA) |
| Traçabilité | Loki, SIEM | Perte/altération des journaux | Investigation impossible |

## Atelier 2 — Sources de risque

Script kiddie / testeur interne (notre PC Attaquant), erreur de configuration,
composant à privilèges excessifs (le moteur de remédiation lui-même).

## Atelier 3-4 — Scénarios

| Scénario | Vraisemblance (1-4) | Gravité (1-4) | Niveau |
|----------|:---:|:---:|:---:|
| Flood → indisponibilité API | 4 | 3 | **Élevé** |
| Injection SQL via l'API | 3 | 4 | **Élevé** |
| Moteur de remédiation détourné (droits Docker) | 2 | 4 | **Élevé** |
| Secret exposé dans le dépôt | 3 | 3 | Moyen |
| Faux positif ML → remédiation inutile | 3 | 2 | Moyen |

## Atelier 5 — Traitement

| Risque | Mesure | Où dans le projet |
|--------|--------|-------------------|
| Flood | Rate-limit WAF + remédiation auto (restart/isolation) | gateway, remediation-engine |
| Injection SQL | WAF (OWASP CRS) + requêtes paramétrées | gateway, payment-api |
| Remédiation détournée | Proxy socket Docker en moindre privilège | docker-socket-proxy |
| Secret exposé | SOPS + .gitignore | .sops.yaml |
| Faux positif ML | Seuil + fenêtre de confirmation avant action | ml-detector |

## Objectifs de continuité (cohérents avec le démonstrateur)

- **RTO** visé en démo : < 60 s (reprise automatique observable dans le Clip Chrono).
- **RPO** : 0 sur les transactions validées (persistées en base avant acquittement).

Ces chiffres doivent être **prouvés** par la démo, pas seulement annoncés.
