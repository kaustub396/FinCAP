// Thin fetch helpers shared by all pages.
async function get(path) {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`)
  return r.json()
}

async function post(path) {
  const r = await fetch(path, { method: 'POST' })
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try {
      const body = await r.json()
      if (body.detail) detail = body.detail
    } catch { /* keep status */ }
    throw new Error(detail)
  }
  return r.json()
}

export const api = {
  health: () => get('/api/health'),
  status: () => get('/api/status'),
  log: () => get('/api/log'),
  results: () => get('/api/results'),
  equity: () => get('/api/equity'),
  published: () => get('/api/published'),
  regimes: () => get('/api/regimes'),
  coverage: () => get('/api/coverage'),
  run: (mode) => post(`/api/run/${mode}`),
}

export function fmtPct(x, digits = 2) {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  return `${(x * 100).toFixed(digits)}%`
}

export function fmtNum(x, digits = 3) {
  if (x === null || x === undefined || Number.isNaN(x)) return '—'
  return Number(x).toFixed(digits)
}
