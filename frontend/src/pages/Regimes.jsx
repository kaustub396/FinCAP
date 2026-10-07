import { useEffect, useMemo, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceArea,
} from 'recharts'
import { api } from '../api.js'

// Build contiguous bear (regime 1) segments for ReferenceArea bands
function bearSegments(series) {
  const segs = []
  let start = null
  series.forEach(([date, , regime], i) => {
    if (regime === 1 && start === null) start = date
    const next = series[i + 1]
    const endsHere = start !== null && (!next || next[2] !== 1)
    if (endsHere) {
      segs.push({ x1: start, x2: date })
      start = null
    }
  })
  return segs
}

export default function Regimes() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.regimes().then(setData).catch((e) => setError(String(e)))
  }, [])

  const chartData = useMemo(
    () => (data?.series ?? []).map(([date, close, regime]) => ({ date, close, regime })),
    [data],
  )
  const segs = useMemo(() => bearSegments(data?.series ?? []), [data])

  if (error) return <div className="error-box">{error}</div>
  if (!data) return <div className="loading">Fitting 2-state Gaussian HMM…</div>

  const counts = data.counts ?? {}
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1
  const bull = counts['0'] ?? 0
  const bear = counts['1'] ?? 0

  return (
    <>
      <div className="page-head">
        <h2>
          Market Regimes{' '}
          <span className={`badge ${data.demo ? 'demo' : 'live'}`}>
            {data.demo ? (data.source === 'real' ? 'REAL INDEX' : 'SYNTHETIC INDEX') : 'LIVE RUN'}
          </span>
        </h2>
        <p>
          2-state Gaussian HMM on index features (returns, volatility, drawdown, trend, ATR).
          States ordered by mean 20-day return: <b>0 = calm/bull</b>, <b>1 = stressed/bear</b>.
          The GP search is conditioned on these regimes in the full architecture.
        </p>
      </div>

      <div className="grid kpi">
        <div className="card kpi">
          <div className="label">Calm State (0) Days</div>
          <div className="value pos">{bull}</div>
          <div className="sub">{((bull / total) * 100).toFixed(1)}% of sample</div>
        </div>
        <div className="card kpi">
          <div className="label">Stressed State (1) Days</div>
          <div className="value neg">{bear}</div>
          <div className="sub">{((bear / total) * 100).toFixed(1)}% of sample</div>
        </div>
        <div className="card kpi">
          <div className="label">Regime Split Ratio</div>
          <div className="value">{(bull / Math.max(bear, 1)).toFixed(2)}</div>
          <div className="sub">calm : stressed</div>
        </div>
      </div>

      <div className="card mt">
        <h3>Index Price with Regime Overlay (red bands = stressed state)</h3>
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#223052" strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={50} stroke="#8fa3c0" fontSize={11}
                    tickFormatter={(d) => d.slice(0, 7)} />
            <YAxis stroke="#8fa3c0" fontSize={11} domain={['auto', 'auto']}
                   tickFormatter={(v) => Number(v).toFixed(0)} />
            <Tooltip
              contentStyle={{ background: '#131f36', border: '1px solid #223052', borderRadius: 8 }}
              labelStyle={{ color: '#8fa3c0' }}
              formatter={(v, k) => (k === 'close' ? [Number(v).toFixed(1), 'Index'] : [v, k])}
            />
            {segs.map((s, i) => (
              <ReferenceArea key={i} x1={s.x1} x2={s.x2}
                             fill="#f0566b" fillOpacity={0.10} />
            ))}
            <Line type="monotone" dataKey="close" stroke="#35d0ef" strokeWidth={1.8}
                  dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        <div className="muted" style={{ fontSize: 12 }}>
          {data.demo
            ? 'Demo mode: HMM fitted live on the synthetic index (or real NIFTY50 index when the processed panel is present).'
            : 'HMM fitted during the live pipeline run.'}
        </div>
      </div>
    </>
  )
}
