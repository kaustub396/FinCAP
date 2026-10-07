import { useEffect, useState } from 'react'
import { api } from './api.js'
import Overview from './pages/Overview.jsx'
import Pipeline from './pages/Pipeline.jsx'
import Formulas from './pages/Formulas.jsx'
import Regimes from './pages/Regimes.jsx'
import DataPage from './pages/DataPage.jsx'

const NAV = [
  { id: 'overview', label: 'Overview', ico: '▦', comp: Overview },
  { id: 'pipeline', label: 'Run Pipeline', ico: '▶', comp: Pipeline },
  { id: 'formulas', label: 'Discovered Alphas', ico: 'ƒ', comp: Formulas },
  { id: 'regimes', label: 'Market Regimes', ico: '∿', comp: Regimes },
  { id: 'data', label: 'Data & Coverage', ico: '▤', comp: DataPage },
]

export default function App() {
  const [page, setPage] = useState('overview')
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  const Current = NAV.find((n) => n.id === page)?.comp ?? Overview

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <h1>FinCAP</h1>
          <div className="tag">Two-Stage LLM × Genetic Programming</div>
        </div>
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`nav-btn ${page === n.id ? 'active' : ''}`}
            onClick={() => setPage(n.id)}
          >
            <span className="ico">{n.ico}</span> {n.label}
          </button>
        ))}
        <div className="footer">
          <div>
            <span className={`dot ${health ? '' : 'off'}`} />
            API {health ? 'connected' : 'unreachable'}
          </div>
          {health && (
            <>
              <div>LLM weights: {health.llm_weights_available ? 'local ✓' : 'not found (rules)'}</div>
              <div>Real panel: {health.real_panel_available ? '✓' : 'absent → synthetic'}</div>
            </>
          )}
        </div>
      </aside>
      <main className="main">
        <Current />
      </main>
    </div>
  )
}
