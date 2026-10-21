Synthèse du projet PROJECT RESILIENCE-ALPHA
Ce document résume les faits essentiels du projet. Il sert de référence et alimente l'assistant RAG.

Objectif du projet
PROJECT RESILIENCE-ALPHA est un démonstrateur de cyber-résilience. Il montre qu'un système d'information de paiement fictif peut détecter une attaque, décider d'une remédiation et l'exécuter seul, sans aucune intervention humaine, puis prouver que le service est de nouveau utilisable. C'est une reprise autonome, aussi appelée reprise zero-touch.

Les 5 piliers du projet
Le projet est organisé en cinq piliers obligatoires :

Développement : la Payment API, le service d'authentification et le dashboard frontend. Technologies : FastAPI pour l'API et l'authentification, React et Tailwind pour le dashboard.
Infrastructure : l'orchestration Docker Compose, les playbooks Ansible, et l'observabilité avec Prometheus, Grafana, Loki et Promtail.
IA et Data : le détecteur d'anomalies par machine learning (Isolation Forest) et l'assistant RAG basé sur un modèle de langage local (Ollama, modèle inférieur ou égal à 8 milliards de paramètres) avec LangChain et Chroma.
Cybersécurité : le pare-feu applicatif WAF (ModSecurity avec les règles OWASP CRS), les scénarios d'attaque, le chiffrement des secrets avec SOPS, et le durcissement des accès.
Gouvernance : l'analyse de risques EBIOS RM, le plan de continuité et de reprise PCA/PRA, et l'analyse de conformité NIS2 et DORA.
La boucle de reprise autonome
La boucle de reprise est le cœur du projet. Elle fonctionne en quatre temps : détecter, décider, agir, vérifier.

Détecter : Prometheus collecte les métriques (débit, taux d'erreur, latence) toutes les 5 secondes. Le détecteur ML compare au comportement normal appris et lève une anomalie.
Décider : le détecteur envoie un incident au moteur de remédiation, précisant le service touché et le type d'effet observé.
Agir : le moteur de remédiation redémarre le service touché, via un proxy du socket Docker en moindre privilège.
Vérifier : le moteur exécute une transaction de contrôle. Le service n'est considéré comme rétabli que s'il répond réellement. Un simple conteneur redémarré ne suffit pas comme preuve.
Aucune intervention humaine n'a lieu entre l'anomalie et le retour à la normale.

Objectifs de continuité : RTO et RPO
Le RTO, Recovery Time Objective ou temps de reprise visé, est inférieur à 60 secondes. Il est mesuré en direct par le moteur de remédiation et affiché pendant la démonstration. En pratique, le temps de reprise observé se situe entre 10 et 35 secondes selon le moment de l'attaque.

Le RPO, Recovery Point Objective ou perte de données maximale, est de zéro sur les transactions validées : elles sont enregistrées en base de données avant d'être acquittées, donc rien n'est perdu.

Les deux scénarios d'attaque
Le projet distingue deux menaces de nature différente, qui appellent deux réponses différentes.

Attaque principale, le flood : un épuisement de ressources sur la Payment API. C'est une atteinte à la disponibilité. L'API sature, la latence explose et des erreurs apparaissent. La réponse est la remédiation automatique : le moteur restaure la disponibilité en redémarrant le service.

Attaque secondaire, l'injection SQL : une tentative de compromission des données. La réponse n'est pas de redémarrer, mais de bloquer. Le pare-feu WAF reconnaît le motif d'injection et renvoie une erreur 403, avant même l'authentification, et journalise l'événement.

Distinguer la disponibilité de la compromission est un point clé : on ne répond pas à une injection SQL par un redémarrage.

Le détecteur d'anomalies par machine learning
Le détecteur utilise un modèle Isolation Forest, un algorithme non supervisé. Il n'utilise aucun seuil codé en dur. Au démarrage, il observe le trafic normal pendant environ 60 secondes et apprend ce qui est normal. Ensuite, il repère tout comportement atypique. Il exige trois anomalies consécutives avant de déclencher, pour éviter les faux positifs. Le détecteur ne corrige rien lui-même : il détecte et alerte, la correction est le rôle du moteur de remédiation.

L'assistant RAG
L'assistant RAG aide un opérateur à consulter les procédures et comprendre un incident. Il utilise un modèle de langage local via Ollama, inférieur ou égal à 8 milliards de paramètres, avec LangChain et Chroma. Les embeddings sont calculés par un modèle dédié, nomic-embed-text, et la génération par llama3.1:8b. L'assistant est en lecture seule et n'a aucun privilège système. Aucune donnée ne sort du système : tout reste local.

Choix de sécurité
Le moteur de remédiation n'accède jamais au socket Docker en direct. Il passe par un proxy qui n'autorise que lister et redémarrer des conteneurs, pas la création d'images, ni l'accès aux volumes, ni l'exécution de commandes. C'est le principe du moindre privilège.

La base de données, les secrets, Prometheus et le moteur de remédiation sont sur un réseau interne et ne sont jamais exposés sur le réseau. Seuls le dashboard, l'API via le WAF et Grafana sont accessibles.

Les secrets sont chiffrés avec SOPS. Aucun secret n'apparaît en clair dans l'archive de rendu. Les mots de passe sont hachés avec bcrypt.

Limites assumées
Le projet est un prototype de 4 jours, pas une plateforme de paiement industrielle. Le modèle ML apprend sur un baseline court. La remédiation couvre la disponibilité, pas la correction d'une compromission. Il n'y a pas de bascule multi-site : une panne matérielle du PC Hôte entraîne une interruption.