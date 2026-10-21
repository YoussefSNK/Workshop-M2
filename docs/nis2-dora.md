# NIS2 & DORA — lecture pour une activité financière fictive — G<n>

Objectif : distinguer les exigences **pertinentes et illustrées** par le prototype de celles
qui **ne peuvent pas** être démontrées en quatre jours. Un rapport de conformité générique ne
suffit pas : chaque point est rattaché à un élément concret de la solution.

## NIS2 (sécurité des réseaux et de l'information)

| Exigence | Démontrable ici ? | Où / pourquoi |
|----------|:---:|----------------|
| Gestion des incidents | Oui | Détection ML + remédiation + journalisation des incidents |
| Journalisation & traçabilité | Oui | Loki (logs), SIEM/WAF (événements) |
| Mesures de sécurité (durcissement, accès) | Partiel | Moindre privilège du moteur, secrets SOPS, réseau interne |
| Notification d'incident aux autorités (72h) | Non | Processus organisationnel, hors prototype |
| Analyse de risques & gouvernance | Oui | EBIOS RM (ce dossier) |

## DORA (résilience opérationnelle numérique du secteur financier)

| Exigence | Démontrable ici ? | Où / pourquoi |
|----------|:---:|----------------|
| Tests de résilience opérationnelle | Oui | Chaos/attaque + preuve de reprise automatique |
| Détection et réponse aux incidents TIC | Oui | Chaîne détection → remédiation → vérification |
| Objectifs de continuité (RTO/RPO) | Oui | RTO < 60 s mesuré, RPO 0 |
| Gestion du risque lié aux tiers (TIC) | Non | Contrats fournisseurs, hors prototype |
| Partage d'informations sur les menaces | Non | Dispositif sectoriel, hors prototype |

## Recommandation à la direction (posture conseil)

Le prototype prouve la **capacité technique** de détection et de reprise automatique (cœur de
DORA et de la gestion d'incident NIS2). Les obligations **organisationnelles** (notification
réglementaire, gouvernance tierce, tests périodiques formalisés) restent à instruire hors de ce
cadre. Priorité recommandée : industrialiser la journalisation et la notification d'incident,
car c'est le premier point contrôlé en cas d'audit.
