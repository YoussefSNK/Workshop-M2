# docker-restart-proxy — moindre privilège réel

Mini-proxy nginx devant le socket Docker. Le moteur de remédiation ne parle jamais au socket
en direct : il passe par ce proxy, qui n'autorise **que** les routes nécessaires au redémarrage
d'un conteneur et renvoie **403 sur tout le reste**.

## Pourquoi pas `tecnativa/docker-socket-proxy`

Le proxy tecnativa fonctionne par famille de ressources : `CONTAINERS=1` autorise **tout**
`/containers` (lister, inspecter, mais aussi `create`, `stop`, `start`). `ALLOW_RESTARTS`
regroupe `stop|restart|kill`, et il n'existe pas de règle pour refuser `stop`/`start`/`create`
tant que `CONTAINERS=1`. On ne peut donc pas y obtenir « restart uniquement » — vérifié :
`POST /containers/create` et `/stop` passent malgré le durcissement.

Ici, l'allowlist est explicite et lisible (voir `nginx.conf`) :

| Route | Méthode | But |
|---|---|---|
| `/version`, `/_ping` | GET | handshake du client Docker |
| `/<api>/containers/json` | GET | lister les conteneurs |
| `/<api>/containers/<id>/json` | GET | inspecter (requis par le SDK avant restart) |
| `/<api>/containers/<id>/restart` | POST | **seule** action d'écriture autorisée |
| tout le reste | — | **403** |

Le socket est monté en lecture seule, mais c'est l'allowlist nginx qui fait la vraie limite :
même un `POST /containers/create` est refusé avant d'atteindre le socket.
