import { useEffect, useState } from 'react'
import { api, fmtNum } from '../api.js'

function ScorePill({ score }) {
  if (score == null) return <span className="muted">—</span>
  return <span className={`score-pill score-${score}`}>{score}/5</span>
}

export default function Formulas() {
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.results().then(setResults).catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!results) return <div className="loading">Loading candidates…</div>

  const formulas = results.formulas ?? []
  const demo = results.run?.demo !== false

  return (
    <>
      <div className="page-head">
        <h2>
          Discovered Alphas{' '}
          <span className={`badge ${demo ? 'demo' : 'live'}`}>
            {demo ? 'DEMO SET' : 'LIVE RUN'}
          </span>
        </h2>
        <p>
          Candidates surviving the validation IC gate, scored by Stage 1 (economic sanity judge).
          Scores ≤ 2 are routed to Stage 2 for closed-vocabulary repair, then re-checked by
          AST compilation and out-of-sample IC before acceptance.
        </p>
      </div>

      {formulas.length === 0 && <div className="loading">No candidates yet — run the pipeline.</div>}

      {formulas.map((f, i) => (
        <div className="formula-card" key={i}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <ScorePill score={f.stage1_score} />
              <span className={`status-chip status-${f.status}`}>{f.status}</span>
              <span className="muted" style={{ fontSize: 12 }}>#{i + 1} · seed {f.seed}</span>
            </div>
            <div className="formula-meta">
              <span>val IC <b>{fmtNum(f.val_ic, 4)}</b></span>
              <span>ICIR <b>{fmtNum(f.val_icir, 3)}</b></span>
              <span>tree <b>{f.tree_size}</b></span>
            </div>
          </div>

          <div className="formula-expr">Alpha = {f.formula}</div>

          {f.mutation && (
            <div className="arrow-row">
              <span className="muted" style={{ fontSize: 12 }}>Stage 2 repair:</span>
            </div>
          )}
          {f.mutation && (
            <div className="formula-expr mutated">Alpha = {f.mutation}</div>
          )}
          {f.mutation_note && (
            <div className="muted" style={{ fontSize: 12, marginTop: -4 }}>{f.mutation_note}</div>
          )}

          {f.stage1_reason && <div className="formula-reason">“{f.stage1_reason}”</div>}
        </div>
      ))}
    </>
  )
}
