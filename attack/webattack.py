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
  :root {
    color-scheme: dark;
    --bg:#0d1117; --bg2:#0a0e14; --card:#161b22; --card2:#1c232d;
    --line:#2a313c; --fg:#e8ebf0; --muted:#9aa4b2; --faint:#6b7483;
    --accent:#d97706; --accent-soft:#2a2113; --danger:#e5484d; --ok:#2fb86a;
    --radius:12px;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; padding:32px 20px 48px;
    font-family:"Segoe UI",system-ui,sans-serif;
    background:var(--bg);
    color:var(--fg); line-height:1.5;
  }
  /* Fond anime : grille de points deformee par la souris (canvas 2D, derriere le contenu) */
  #bg { position:fixed; inset:0; width:100%; height:100%; z-index:0; display:block; }
  .wrap { max-width:760px; margin:0 auto; position:relative; z-index:1; }

  header { display:flex; align-items:baseline; gap:12px; padding-bottom:18px;
           border-bottom:1px solid var(--line); margin-bottom:24px; }
  header .tag { font-family:ui-monospace,monospace; font-size:.72rem; letter-spacing:.12em;
                text-transform:uppercase; color:var(--accent);
                border:1px solid var(--accent); border-radius:6px; padding:3px 9px; }
  header h1 { font-size:1.15rem; font-weight:600; margin:0; }
  header p { margin:0; color:var(--muted); font-size:.82rem; }

  .card { background:rgba(22,27,34,.92); backdrop-filter:blur(2px);
          border:1px solid var(--line); border-radius:var(--radius);
          padding:20px 22px; margin:16px 0; }
  .card h2 { font-size:.78rem; letter-spacing:.1em; text-transform:uppercase;
             color:var(--faint); margin:0 0 4px; font-weight:600; }
  .card .sub { color:var(--muted); font-size:.85rem; margin:0 0 14px; }

  label { display:block; font-size:.74rem; letter-spacing:.03em; color:var(--muted);
          margin:12px 0 5px; text-transform:uppercase; }
  input { width:100%; padding:10px 12px; border-radius:9px; border:1px solid var(--line);
          background:var(--bg2); color:var(--fg); font-size:.95rem; font-family:ui-monospace,monospace; }
  input:focus { outline:none; border-color:var(--accent); }
  .row { display:flex; gap:14px; } .row > div { flex:1; }

  .cardhead { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }

  button { border:1px solid transparent; border-radius:9px; padding:11px 18px;
           font-size:.9rem; font-weight:600; cursor:pointer; margin:14px 10px 0 0;
           transition:filter .15s, border-color .15s; }
  button:hover { filter:brightness(1.12); }
  .attack { background:var(--accent); color:#1a1205; }
  .stop   { background:transparent; color:var(--muted); border-color:var(--line); }
  .sqli   { background:transparent; color:var(--accent); border-color:var(--accent); }

  .grid { display:flex; gap:28px; margin-top:16px;
          padding:16px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
  .grid > div { flex:1; }
  .stat { font-size:2.4rem; font-weight:700; font-variant-numeric:tabular-nums;
          font-family:ui-monospace,monospace; letter-spacing:-.02em; }
  .stat.err { color:var(--danger); }
  .grid label { margin-top:2px; }

  .pill { display:inline-flex; align-items:center; gap:7px; padding:5px 12px; border-radius:999px;
          font-size:.74rem; font-weight:600; border:1px solid var(--line); color:var(--muted); }
  .pill::before { content:""; width:7px; height:7px; border-radius:50%; background:currentColor; }
  .pill.idle { color:var(--faint); }
  .pill.run  { color:var(--danger); border-color:var(--danger); background:#2a1416;
               animation:pulse 1.1s ease-in-out infinite; }
  .pill.done { color:var(--ok); border-color:var(--ok); background:#102a1c; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }

  .result { margin-top:12px; font-family:ui-monospace,monospace; font-size:.88rem; }
  .result .code { display:inline-block; padding:2px 9px; border-radius:6px; font-weight:700; margin-right:8px; }
  .ok  { color:var(--ok); }  .ok .code { background:#102a1c; border:1px solid var(--ok); }
  .bad { color:var(--danger); } .bad .code { background:#2a1416; border:1px solid var(--danger); }

  .log { font-family:ui-monospace,monospace; font-size:.8rem; color:var(--muted);
          white-space:pre-wrap; max-height:170px; overflow:auto;
          background:var(--bg2); border:1px solid var(--line); border-radius:9px; padding:12px; }
  .log:empty::before { content:"En attente d'action…"; color:var(--faint); }
</style></head>
<body>
<canvas id="bg"></canvas>
<div class="wrap">
  <header>
    <span class="tag">PC Attaquant</span>
    <div>
      <h1>Console de démonstration — RESILIENCE-ALPHA</h1>
      <p>Test de charge et requête de contrôle contre le SI fictif (périmètre privé).</p>
    </div>
  </header>

  <div class="card">
    <h2>Cible</h2>
    <label>Adresse du service (privée uniquement : 10.x / 192.168.x / localhost)</label>
    <input id="target" placeholder="http://localhost:8000" value="http://localhost:8000">
    <div class="row">
      <div><label>Durée (s)</label><input id="duration" type="number" value="20" min="1" max="120"></div>
      <div><label>Concurrence</label><input id="concurrency" type="number" value="120" min="1" max="300"></div>
    </div>
  </div>

  <div class="card">
    <div class="cardhead">
      <h2>Attaque principale — Flood (disponibilité)</h2>
      <span id="pill" class="pill idle">inactif</span>
    </div>
    <div class="grid">
      <div><div class="stat" id="sent">0</div><label>requêtes envoyées</label></div>
      <div><div class="stat err" id="errors">0</div><label>erreurs / timeouts</label></div>
    </div>
    <button class="attack" onclick="startFlood()">Lancer le flood</button>
    <button class="stop" onclick="stopFlood()">Stop</button>
  </div>

  <div class="card">
    <h2>Attaque secondaire — Injection SQL (compromission)</h2>
    <p class="sub">Résultat attendu : <b>403</b> — requête bloquée par le WAF avant l'API.</p>
    <button class="sqli" onclick="runSqli()">Envoyer l'injection SQL</button>
    <div id="sqliResult" class="result"></div>
  </div>

  <div class="card">
    <h2>Journal</h2>
    <div class="log" id="log"></div>
  </div>
</div>

<script>
/* ---- Fond : grille de points, onde de repulsion sous la souris ---- */
(function(){
  const cv = document.getElementById('bg'), ctx = cv.getContext('2d');
  const GAP = 26, DOT = 1.6, RADIUS = 130, PUSH = 22;   // espacement, taille, rayon d'effet, force
  const COLOR = '217,119,6';                            // ambre (--accent) en rgb
  let w, h, cols, rows, dpr;
  const mouse = { x: -9999, y: -9999 };

  function resize(){
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = cv.clientWidth; h = cv.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(w / GAP) + 1; rows = Math.ceil(h / GAP) + 1;
  }
  window.addEventListener('resize', resize); resize();

  window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('mouseleave', () => { mouse.x = mouse.y = -9999; });

  function frame(){
    ctx.clearRect(0, 0, w, h);
    for(let i=0;i<cols;i++){
      for(let j=0;j<rows;j++){
        let x = i*GAP, y = j*GAP;
        const dx = x - mouse.x, dy = y - mouse.y;
        const d = Math.hypot(dx, dy);
        let r = DOT, a = 0.18;
        if(d < RADIUS){
          const f = (1 - d/RADIUS);          // 1 au centre -> 0 au bord
          const ang = Math.atan2(dy, dx);
          x += Math.cos(ang) * f * PUSH;      // repousse le point
          y += Math.sin(ang) * f * PUSH;
          r = DOT + f * 2.4;                  // et l'agrandit
          a = 0.18 + f * 0.7;                 // et l'eclaire
        }
        ctx.fillStyle = 'rgba('+COLOR+','+a.toFixed(3)+')';
        ctx.beginPath(); ctx.arc(x, y, r, 0, 6.2832); ctx.fill();
      }
    }
    if(!document.hidden) requestAnimationFrame(frame);  // pause hors ecran (perf)
  }
  document.addEventListener('visibilitychange', () => { if(!document.hidden) frame(); });
  frame();
})();

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
  if(d.error){ $('sqliResult').innerHTML = `<span class="bad"><span class="code">ERR</span>${d.error}</span>`; return; }
  const cls = d.blocked ? 'ok' : 'bad';
  $('sqliResult').innerHTML = `<span class="${cls}"><span class="code">${d.code ?? '—'}</span>${d.msg}</span>`;
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
