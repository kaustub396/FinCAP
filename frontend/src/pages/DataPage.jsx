import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell,
} from 'recharts'
import { api } from '../api.js'

const FEATURES = [
  'ret_1d', 'ret_5d', 'ret_20d', 'ret_60d', 'ret_120d', 'ret_250d',
  'vol_5d', 'vol_20d', 'vol_60d', 'vol_120d', 'range_pct', 'atr_14',
  'sma_20', 'sma_50', 'sma_200', 'price_to_sma20', 'price_to_sma50',
  'price_to_sma200', 'drawdown_60d', 'drawdown_250d', 'rsi_14',
  'zscore_20', 'zscore_60', 'vol_ratio_5_20', 'vol_change_5d',
  'oc_ratio', 'hl_ratio', 'afm_sentiment', 'afm_fundamental',
]

export default function DataPage() {
  const [coverage, setCoverage] = useState(null)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.coverage(), api.health()])
      .then(([c, h]) => { setCoverage(c); setHealth(h) })
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!coverage || !health) return <div className="loading">Loading data info…</div>

  return (
    <>
      <div className="page-head">
        <h2>Data &amp; Coverage</h2>
        <p>
          Fundamentals panel for Nifty 50 + Bank Nifty (58 companies, 2005–2025) assembled by
          research_data/scripts, plus the technical feature panel consumed by the GP engine.
        </p>
      </div>

      <div className="grid kpi">
        <div className="card kpi">
          <div className="label">Panel Rows</div>
          <div className="value">{coverage.rows}</div>
          <div className="sub">company-years</div>
        </div>
        <div className="card kpi">
          <div className="label">Companies</div>
          <div className="value">{coverage.companies}</div>
          <div className="sub">Nifty 50 + Bank Nifty</div>
        </div>
        <div className="card kpi">
          <div className="label">Year Range</div>
          <div className="value" style={{ fontSize: 24 }}>{coverage.year_range}</div>
          <div className="sub">source: {coverage.source}</div>
        </div>
        <div className="card kpi">
          <div className="label">GP Features</div>
          <div className="value">{FEATURES.length}</div>
          <div className="sub">closed vocabulary</div>
        </div>
      </div>

      <div className="grid two mt">
        <div className="card">
          <h3>Fundamentals Coverage (%)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={coverage.ratios} margin={{ top: 4, right: 12, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="#223052" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" stroke="#8fa3c0" fontSize={11} interval={0} />
              <YAxis stroke="#8fa3c0" fontSize={11} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: '#131f36', border: '1px solid #223052', borderRadius: 8 }}
                labelStyle={{ color: '#8fa3c0' }}
                formatter={(v, _n, p) => [`${p.payload.filled}/${coverage.rows} (${v}%)`, 'filled']}
              />
              <Bar dataKey="pct" radius={[5, 5, 0, 0]}>
                {coverage.ratios.map((_, i) => (
                  <Cell key={i} fill={i % 2 === 0 ? '#0091b3' : '#35d0ef'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="muted" style={{ fontSize: 12 }}>
            Sources: {coverage.sources.join(' · ')}
          </div>
        </div>

        <div className="card">
          <h3>System Status</h3>
          <table className="data">
            <tbody>
              <tr><td>API</td><td className="num" style={{ color: 'var(--green)' }}>connected</td></tr>
              <tr><td>Local LLM weights</td>
                  <td className="num">{health.llm_weights_available
                    ? <span style={{ color: 'var(--green)' }}>found → LLM judge</span>
                    : <span style={{ color: 'var(--yellow)' }}>absent → rule-based judge</span>}</td></tr>
              <tr><td>Processed panel (.pkl)</td>
                  <td className="num">{health.real_panel_available
                    ? <span style={{ color: 'var(--green)' }}>real data</span>
                    : <span style={{ color: 'var(--yellow)' }}>absent → synthetic</span>}</td></tr>
              <tr><td>Fundamentals CSV</td>
                  <td className="num">{health.coverage_csv_available
                    ? <span style={{ color: 'var(--green)' }}>found</span>
                    : <span style={{ color: 'var(--yellow)' }}>absent → demo values</span>}</td></tr>
              <tr><td>Run modes</td><td className="num">{health.run_modes.join(', ')}</td></tr>
            </tbody>
          </table>
          <p className="muted mt" style={{ fontSize: 12 }}>
            Missing items are gitignored by design (datasets, weights, API keys). The app
            degrades gracefully: synthetic panel + rule-based judge keep every screen
            demonstrable. See README “Setup” for restoring real data.
          </p>
        </div>
      </div>

      <div className="card mt">
        <h3>GP Feature Vocabulary (closed set — Stage 2 mutator may only use these)</h3>
        <div className="chip-list">
          {FEATURES.map((f) => <span className="chip" key={f}>{f}</span>)}
        </div>
      </div>
    </>
  )
}
