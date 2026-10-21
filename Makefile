.PHONY: up down demo logs reset
up:      ## Construit et démarre toute la plateforme
	docker compose up -d --build
down:    ## Arrête la plateforme
	docker compose down
reset:   ## Arrête + supprime les volumes (rejouer une démo propre)
	docker compose down -v
demo:    ## Joue la démo bout-en-bout (avant/attaque/remédiation/après)
	./scripts/demo.sh
logs:    ## Suit les logs des composants clés
	docker compose logs -f ml-detector remediation-engine
