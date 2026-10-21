# PCA / PRA — PROJECT RESILIENCE-ALPHA — G<n>

Plan de continuité et de reprise adapté à la solution réellement livrée.

## Périmètre couvert

| Fonction | Criticité | Couvert par le démonstrateur |
|----------|-----------|------------------------------|
| Traitement d'une transaction | Vitale | Oui — service rétabli automatiquement |
| Authentification | Vitale | Oui |
| Supervision / alerte | Importante | Oui (Prometheus/Loki/Grafana + ML) |
| Assistant opérateur (RAG) | Confort | Partiel (dépend d'Ollama) |

## Scénarios et réponses

| Scénario | Type | Réponse | Automatique ? |
|----------|------|---------|:---:|
| Flood → indisponibilité API | Disponibilité | Redémarrage ciblé + vérification du retour | Oui |
| Injection SQL | Compromission | Blocage WAF + trace SIEM (pas de redémarrage) | Oui (blocage) |
| Corruption de données | Intégrité | Hors périmètre 4 jours — restauration manuelle depuis sauvegarde | Non |

## Objectifs

- RTO (reprise) visé : < 60 s, mesuré par le moteur de remédiation et visible au Clip Chrono.
- RPO (perte de données) : 0 sur les transactions validées (persistées avant acquittement).

## Choix de restauration

La reprise privilégie la **disponibilité** : on remet le service en état de répondre, vérifié
par une transaction de contrôle. Une compromission n'est pas « réparée » par un redémarrage ;
elle est bloquée et tracée pour investigation.

## Risques résiduels après reprise

- Le redémarrage restaure la disponibilité mais n'élimine pas la cause (l'attaquant peut réitérer).
- Un faux négatif du modèle ML retarde la détection → surveillance humaine complémentaire conseillée.
- Pas de bascule multi-site (hors périmètre) : panne matérielle du PC Hôte = interruption.

## Responsabilités (démo)

| Rôle | Responsable |
|------|-------------|
| Déclenchement / supervision | Opérateur (dashboard + Grafana) |
| Détection | Détecteur ML (automatique) |
| Décision + action | Moteur de remédiation (automatique) |
| Investigation post-incident | Équipe sécurité (logs Loki + SIEM) |
