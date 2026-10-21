# Secrets (SOPS)

- `secrets.example.yaml` : modèle en clair (committable).
- `secrets.yaml` : vos vraies valeurs, JAMAIS committé (voir .gitignore).
- `secrets.enc.yaml` : version chiffrée par SOPS, committable.

Chiffrer :  `sops --encrypt secrets/secrets.yaml > secrets/secrets.enc.yaml`
Déchiffrer vers l'environnement au déploiement :
  `sops --decrypt secrets/secrets.enc.yaml` puis injecter dans .env.
Aucun secret ne doit apparaître en clair dans l'archive de rendu (exigence du sujet).
