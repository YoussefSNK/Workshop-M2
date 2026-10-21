import React, { useEffect, useState } from 'react'

// Le dashboard parle uniquement à son propre nginx, qui relaie vers les services
// internes (voir nginx.conf) : /auth, /api (via le WAF), /remediation.
async function jget(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url} -> ${r.status}`)
  return r.json()
}

function StatusDot({ ok }) {
  const c = ok === null ? 'bg-slate-400' : ok ? 'bg-emerald-500' : 'bg-red-500'
  return <span className={`inline-block w-3 h-3 rounded-full ${c}`} />
}

function ServiceCard({ s }) {
  const up = s.container === 'running'
  const bad = s.healthy === false || !up
  return (
    <div className={`rounded-xl border p-4 ${bad ? 'border-red-300 bg-red-50' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-center justify-between">
        <span className="font-medium">{s.service}</span>
        <StatusDot ok={s.healthy === null ? up : s.healthy && up} />
      </div>
      <div className="text-sm text-slate-500 mt-1">conteneur : {s.container}</div>
      {s.healthy !== null && (
        <div className="text-sm text-slate-500">répond : {s.healthy ? 'oui' : 'non'}</div>
      )}
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

  return (
    <div className="min-h-screen bg-slate-100 text-slate-800">
      <header className="bg-slate-900 text-white px-6 py-4">
        <h1 className="text-lg font-semibold">PROJECT RESILIENCE-ALPHA — Supervision</h1>
        <p className="text-slate-300 text-sm">Cyber-résilience et reprise autonome</p>
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-8">
        <section>
          <h2 className="font-medium mb-3">État des services</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {services.map(s => <ServiceCard key={s.service} s={s} />)}
          </div>
        </section>

        <section>
          <h2 className="font-medium mb-3">Transaction de contrôle</h2>
          <button onClick={runTransaction}
            className="bg-slate-900 text-white rounded-lg px-4 py-2 hover:bg-slate-700">
            Exécuter une transaction fictive
          </button>
          {log && <span className="ml-4 text-sm">{log}</span>}
        </section>

        <section>
          <h2 className="font-medium mb-3">Incidents & remédiation</h2>
          <div className="bg-white rounded-xl border border-slate-200 divide-y">
            {incidents.length === 0 && <div className="p-4 text-slate-400 text-sm">Aucun incident.</div>}
            {incidents.map(i => (
              <div key={i.id} className="p-4 flex items-center justify-between">
                <div>
                  <span className="font-mono text-sm">{i.id}</span>
                  <span className="ml-3 text-sm">{i.service} · {i.effect}</span>
                </div>
                <div className="text-sm text-right">
                  <span className={i.recovered ? 'text-emerald-600' : 'text-amber-600'}>{i.status}</span>
                  {i.rto_seconds != null && <span className="ml-3 text-slate-500">RTO {i.rto_seconds}s</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}
