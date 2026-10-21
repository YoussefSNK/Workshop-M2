# Moteur de remédiation

FastAPI. Reçoit un incident, redémarre le service touché via le proxy Docker (moindre
privilège), vérifie le retour à la normale (transaction de contrôle), mesure le RTO.
Expose /incident, /incidents, /status. Voir app.py.
