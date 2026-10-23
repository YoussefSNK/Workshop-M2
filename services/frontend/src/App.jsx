import React, { useEffect, useState } from 'react'

// Le dashboard parle uniquement à son propre nginx, qui relaie vers les services
// internes (voir nginx.conf) : /auth, /api (via le WAF), /remediation.
async function jget(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} -> ${r.status}`)
  return r.json()
}

function StatusDot({ ok }) {
  const c = ok === null ? 'bg-slate-500' : ok ? 'bg-emerald-400' : 'bg-red-500'
  const ring = ok === false ? 'ring-4 ring-red-500/30 animate-pulse' : ''
  return <span className={`inline-block w-3 h-3 rounded-full ${c} ${ring}`} />
}

function ServiceCard({ s }) {
  const up = s.container === 'running'
  const bad = s.healthy === false || !up
  return (
    <div className={`rounded-xl border p-4 transition-colors ${
      bad ? 'border-red-500/50 bg-red-500/10' : 'border-slate-700 bg-slate-800/60'
    }`}>
      <div className="flex items-center justify-between">
        <span className="font-medium text-slate-100">{s.service}</span>
        <StatusDot ok={s.healthy === null ? up : s.healthy && up} />
      </div>
      <div className="text-sm text-slate-400 mt-2">conteneur : <span className="text-slate-200">{s.container}</span></div>
      {s.healthy !== null && (
        <div className="text-sm text-slate-400">répond :
          <span className={s.healthy ? 'text-emerald-400' : 'text-red-400'}> {s.healthy ? 'oui' : 'non'}</span>
        </div>
      )}
    </div>
  )
}

// Bannière d'état globale, dérivée de l'état réel (services + dernier incident).
function StateBanner({ phase, rto }) {
  const conf = {
    nominal:  { label: 'SYSTÈME NOMINAL',   sub: 'Tous les services répondent',
                cls: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300', dot: 'bg-emerald-400' },
    incident: { label: 'INCIDENT EN COURS',  sub: 'Service dégradé — détection et remédiation automatiques',
                cls: 'bg-red-500/15 border-red-500/50 text-red-300 animate-pulse', dot: 'bg-red-500' },
    recovered:{ label: 'REPRISE VÉRIFIÉE',   sub: rto != null ? `Service rétabli — RTO ${rto}s` : 'Service rétabli',
                cls: 'bg-sky-500/15 border-sky-500/40 text-sky-300', dot: 'bg-sky-400' },
  }[phase]
  return (
    <div className={`rounded-2xl border px-6 py-5 flex items-center gap-4 ${conf.cls}`}>
      <span className={`inline-block w-4 h-4 rounded-full ${conf.dot}`} />
      <div>
        <div className="text-xl font-bold tracking-wide">{conf.label}</div>
        <div className="text-sm opacity-80">{conf.sub}</div>
      </div>
    </div>
  )
}

export default function App() {
  const [services, setServices] = useState([])
  const [incidents, setIncidents] = useState([])
  const [log, setLog] = useState('')

  useEffect(() => {
    const tick = async () => {
      try { setServices(await jget('/remediation/status')) } catch {}
      try { setIncidents(await jget('/remediation/incidents')) } catch {}
    }
    tick()
    const id = setInterval(tick, 3000)
    return () => clearInterval(id)
  }, [])

  async function runTransaction() {
    setLog('Transaction en cours...')
    try {
      const auth = await fetch('/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'alice', password: 'alice-pw' }),
      }).then(r => r.json())
      const tx = await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.access_token}` },
        body: JSON.stringify({ from_account: 'ACC-ALICE', to_account: 'ACC-BOB', amount: 10 }),
      })
      setLog(tx.ok ? `Transaction OK (${(await tx.json()).id})` : `Échec : HTTP ${tx.status}`)
    } catch (e) {
      setLog(`Échec : ${e.message}`)
    }
  }

  // --- Phase globale, à partir de l'état réel ---
  // Incident en cours = soit un service tombé, soit un incident reçu mais pas encore résolu
  // (statut in_progress) : la bannière rouge reste visible pendant toute la remédiation.
  const anyDown = services.some(s => s.container !== 'running' || s.healthy === false)
  const last = incidents[0]
  const inProgress = last && last.status === 'in_progress'
  const recentlyRecovered = last && last.recovered && last.received_at &&
    (Date.now() - new Date(last.received_at).getTime()) < 30000  // résolu il y a < 30 s
  const phase = (anyDown || inProgress) ? 'incident' : (recentlyRecovered ? 'recovered' : 'nominal')
  const lastRto = last && last.recovered ? last.rto_seconds : null
  const okTx = log.startsWith('Transaction OK')

  return (
    <div className="min-h-screen bg-slate-900 text-slate-200">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white">PROJECT RESILIENCE-ALPHA</h1>
            <p className="text-slate-400 text-sm">Supervision — cyber-résilience et reprise autonome</p>
          </div>
          <span className="text-xs font-mono text-slate-500 border border-slate-700 rounded px-2 py-1">
            PC Hôte · live
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-8">
        <StateBanner phase={phase} rto={lastRto} />

        <section>
          <h2 className="font-medium mb-3 text-slate-300">État des services</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {services.length === 0
              ? <div className="col-span-full text-slate-500 text-sm">En attente de l'état des services…</div>
              : services.map(s => <ServiceCard key={s.service} s={s} />)}
          </div>
        </section>

        <section>
          <h2 className="font-medium mb-3 text-slate-300">Transaction de contrôle</h2>
          <div className="flex items-center gap-4">
            <button onClick={runTransaction}
              className="bg-sky-600 text-white font-medium rounded-lg px-5 py-2.5 hover:bg-sky-500 transition-colors">
              Exécuter une transaction fictive
            </button>
            {log && (
              <span className={`text-sm font-mono ${okTx ? 'text-emerald-400' : log.startsWith('Échec') ? 'text-red-400' : 'text-slate-400'}`}>
                {log}
              </span>
            )}
          </div>
        </section>

        <section>
          <h2 className="font-medium mb-3 text-slate-300">Incidents &amp; remédiation</h2>
          <div className="bg-slate-800/60 rounded-xl border border-slate-700 divide-y divide-slate-700">
            {incidents.length === 0 && <div className="p-4 text-slate-500 text-sm">Aucun incident.</div>}
            {incidents.map(i => (
              <div key={i.id} className="p-4 flex items-center justify-between">
                <div>
                  <span className="font-mono text-sm text-slate-300">{i.id}</span>
                  <span className="ml-3 text-sm text-slate-400">{i.service} · {i.effect}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    i.recovered ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'
                  }`}>{i.status}</span>
                  {i.rto_seconds != null && (
                    <span className="font-mono text-slate-400">RTO <span className="text-white font-semibold">{i.rto_seconds}s</span></span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}
