import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend,
} from 'recharts'
import { api, fmtPct, fmtNum } from '../api.js'

const CURVE_META = {
  refined: { name: 'Two-Stage Refined GP', color: '#35d0ef', width: 2.5 },
  momentum: { name: 'Momentum Baseline', color: '#e27a1e', width: 1.6 },
  vanilla: { name: 'Vanilla GP', color: '#f0566b', width: 1.6 },
  hmm: { name: 'HMM Regime-GP', color: '#2ecc8f', width: 1.6 },
}

function Kpi({ label, value, sub, tone }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className={`value ${tone ?? ''}`}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

export default function Overview() {
  const [results, setResults] = useState(null)
  const [equity, setEquity] = useState(null)
  const [published, setPublished] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.results(), api.equity(), api.published()])
      .then(([r, e, p]) => { setResults(r); setEquity(e); setPublished(p) })
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!results || !equity || !published) return <div className="loading">Loading overview…</div>

  const demo = results.run?.demo !== false
  const m = results.metrics?.refined ?? {}
  const mom = results.metrics?.momentum

  // Merge all curves onto a common sorted date axis for recharts
  const dateSet = new Set()
  Object.values(equity.curves || {}).forEach((pts) => pts.forEach(([d]) => dateSet.add(d)))
  const chartData = [...dateSet].sort().map((d) => {
    const row = { date: d }
    Object.entries(equity.curves || {}).forEach(([k, pts]) => {
      const hit = pts.find(([dd]) => dd === d)
      if (hit) row[k] = hit[1]
    })
    return row
  })

  return (
    <>
      <div className="page-head">
        <h2>
          Overview{' '}
          <span className={`badge ${demo ? 'demo' : 'live'}`}>
            {demo ? (results.run?.source === 'published' ? 'PUBLISHED RESULTS' : 'DEMO DATA') : 'LIVE RUN'}
          </span>
        </h2>
        <p>
          {demo
            ? results.run?.note || 'Figures below are published paper benchmarks until you run the pipeline.'
            : `Live backtest completed ${results.run?.finished_at} · source: ${results.run?.source} · judge: ${results.run?.judge}`}
        </p>
      </div>

      <div className="grid kpi">
        <Kpi label="OOS Ann. Net Return" value={fmtPct(m.ann_return)}
             tone={m.ann_return >= 0 ? 'pos' : 'neg'} sub="20-day rebalance, costs net" />
        <Kpi label="Net Sharpe" value={fmtNum(m.sharpe)}
             tone={m.sharpe >= 0 ? 'pos' : 'neg'} sub="annualized" />
        <Kpi label="Max Drawdown" value={fmtPct(m.max_drawdown)} tone="neg" sub="peak-to-trough" />
        <Kpi label="Rank IC (OOS)" value={fmtNum(m.rank_ic)} sub={`ICIR ${fmtNum(m.icir)}`} />
        <Kpi label="Win Rate" value={m.win_rate != null ? `${m.win_rate}%` : '—'} sub="rebalance periods" />
      </div>

      <div className="card mt">
        <h3>Cumulative Net Equity (OOS)</h3>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#223052" strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={44} stroke="#8fa3c0" fontSize={11}
                    tickFormatter={(d) => d.slice(0, 7)} />
            <YAxis stroke="#8fa3c0" fontSize={11} domain={['auto', 'auto']} />
            <Tooltip
              contentStyle={{ background: '#131f36', border: '1px solid #223052', borderRadius: 8 }}
              labelStyle={{ color: '#8fa3c0' }}
              formatter={(v, k) => [Number(v).toFixed(4), CURVE_META[k]?.name ?? k]}
            />
            <Legend formatter={(v) => CURVE_META[v]?.name ?? v} />
            {Object.keys(CURVE_META).filter((k) => chartData.some((r) => r[k] != null)).map((k) => (
              <Line key={k} type="monotone" dataKey={k} stroke={CURVE_META[k].color}
                    strokeWidth={CURVE_META[k].width} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
        {equity.demo && <div className="muted" style={{ fontSize: 12 }}>Illustrative curves matching the published results table.</div>}
      </div>

      <div className="grid two mt">
        <div className="card">
          <h3>Published Benchmark Comparison (paper)</h3>
          <table className="data">
            <thead>
              <tr>
                <th>Model Architecture</th>
                <th className="num">Ann. Return</th>
                <th className="num">Sharpe</th>
                <th className="num">Max DD</th>
                <th className="num">S&amp;P 500 Degrad.</th>
              </tr>
            </thead>
            <tbody>
              {published.table.map((row) => (
                <tr key={row.model} className={row.proposed ? 'proposed' : ''}>
                  <td>{row.model}</td>
                  <td className="num">{row.ann_return.toFixed(2)}%</td>
                  <td className="num">{row.sharpe.toFixed(4)}</td>
                  <td className="num">{row.max_drawdown.toFixed(2)}%</td>
                  <td className="num">{row.sp500_degradation.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Live vs Momentum Baseline</h3>
          {mom ? (
            <table className="data">
              <tbody>
                <tr><td>Two-Stage Refined GP</td>
                    <td className="num">{fmtPct(m.ann_return)}</td>
                    <td className="num">{fmtNum(m.sharpe)}</td></tr>
                <tr><td>Momentum Baseline (ret_20d)</td>
                    <td className="num">{fmtPct(mom.ann_return)}</td>
                    <td className="num">{fmtNum(mom.sharpe)}</td></tr>
                <tr><td className="muted">Spread</td>
                    <td className="num">{fmtPct((m.ann_return ?? 0) - (mom.ann_return ?? 0))}</td>
                    <td className="num">{fmtNum((m.sharpe ?? 0) - (mom.sharpe ?? 0))}</td></tr>
              </tbody>
            </table>
          ) : (
            <div className="muted">Momentum baseline unavailable.</div>
          )}
          <p className="muted mt" style={{ fontSize: 12 }}>
            Evaluation: dollar-neutral long/short top-vs-bottom quintile, 20-day rebalance,
            10 bps per side transaction cost, {results.run?.test_days ?? '—'} OOS test days.
          </p>
          <p className="muted" style={{ fontSize: 12 }}>
            Evaluation universe: {published.evaluation.universe} ·
            OOS markets: {published.evaluation.oos_markets.join(', ')} ·
            execution errors: {published.evaluation.execution_errors}.
          </p>
        </div>
      </div>
    </>
  )
}
