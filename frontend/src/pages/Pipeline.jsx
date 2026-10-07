import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

export default function Pipeline() {
  const [status, setStatus] = useState(null)
  const [log, setLog] = useState([])
  const [mode, setMode] = useState('quick')
  const [startError, setStartError] = useState(null)
  const logRef = useRef(null)

  const refresh = useCallback(() => {
    api.status().then(setStatus).catch(() => {})
    api.log().then((r) => setLog(r.entries)).catch(() => {})
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 1500)
    return () => clearInterval(id)
  }, [refresh])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [log])

  const running = status?.running === true

  async function start() {
    setStartError(null)
    try {
      await api.run(mode)
      refresh()
    } catch (e) {
      setStartError(String(e.message || e))
    }
  }

  return (
    <>
      <div className="page-head">
        <h2>Run Pipeline</h2>
        <p>
          HMM regime fit → GP evolution → validation IC gate → Stage 1 judge → Stage 2 mutator
          → ensemble out-of-sample evaluation.
        </p>
      </div>

      <div className="card">
        <div className="controls">
          <select className="mode" value={mode} onChange={(e) => setMode(e.target.value)} disabled={running}>
            <option value="quick">Quick demo (pop 80 · 10 gen · 1 seed, ~2 min)</option>
            <option value="standard">Standard (pop 200 · 30 gen · 2 seeds, ~10 min)</option>
          </select>
          <button className="btn primary" onClick={start} disabled={running}>
            {running ? 'Run in progress…' : '▶  Start Run'}
          </button>
          {status?.finished_at && !running && (
            <span className="muted" style={{ fontSize: 12 }}>
              last run: {status.finished_at} · {status.stage}{status.error ? ' · FAILED' : ''}
            </span>
          )}
        </div>
        {startError && <div className="error-box">{startError}</div>}
        {status?.error && !running && <div className="error-box">Run error: {status.error}</div>}

        <div className="progress-wrap">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${status?.progress ?? 0}%` }} />
          </div>
          <div className="progress-meta">
            <span>{status?.stage ?? 'idle'}{running ? ' …' : ''}</span>
            <span>{status?.progress ?? 0}%</span>
          </div>
        </div>
      </div>

      <div className="card mt">
        <h3>Pipeline Log {running && <span className="muted">— streaming</span>}</h3>
        <div className="log-console" ref={logRef}>
          {log.length === 0 && <span className="muted">No log yet. Start a run to see live output.</span>}
          {log.map((e, i) => (
            <div key={i} className={e.msg.startsWith('ERROR') ? 'err' : e.msg.includes('Judge') ? 'stage' : ''}>
              <span className="t">{e.t}</span>
              {e.msg}
            </div>
          ))}
        </div>
      </div>

      {status && !running && status.has_results && (
        <div className="grid kpi mt">
          <div className="card kpi">
            <div className="label">Fit / Val / Test days</div>
            <div className="value" style={{ fontSize: 20 }}>
              {status.source === 'synthetic' ? 'see log' : 'real panel'}
            </div>
            <div className="sub">source: {status.source}</div>
          </div>
          <div className="card kpi">
            <div className="label">Mode</div>
            <div className="value" style={{ fontSize: 24 }}>{status.mode}</div>
            <div className="sub">GP configuration</div>
          </div>
        </div>
      )}
    </>
  )
}
