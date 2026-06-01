// Thin API client. All requests are same-origin: in dev Vite proxies /api and
// /media to FastAPI; in production Nginx does the same.

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch (e) {
      /* ignore parse error */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  generateScript: (payload) => postJSON('/api/script/generate', payload),
  approveScript: (jobId) => postJSON('/api/script/approve', { job_id: jobId }),
  produce: (payload) => postJSON('/api/video/produce', payload),
  regenerateThumbnail: (jobId, title) =>
    postJSON('/api/thumbnail/regenerate', { job_id: jobId, title }),
  getStats: async () => {
    const res = await fetch('/api/admin/stats')
    if (!res.ok) throw new Error('Failed to load stats')
    return res.json()
  },
  getAlerts: async () => {
    const res = await fetch('/api/news/alerts')
    if (!res.ok) throw new Error('Failed to load alerts')
    return res.json()
  },
  sendTestAlert: () => postJSON('/api/news/test-alert', {}),
  fetchLatestNews: async () => {
    const res = await fetch('/api/news/latest')
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail || detail
      } catch (e) {
        /* ignore */
      }
      throw new Error(detail)
    }
    return res.json()
  },
  progressUrl: (jobId) => `/api/video/progress/${jobId}`,
  downloadUrl: (jobId) => `/api/video/download/${jobId}`,
  // thumbnail.jpg is served from OUTPUT_DIR via /media. Cache-bust on demand.
  thumbnailUrl: (bust) => `/media/thumbnail.jpg${bust ? `?t=${bust}` : ''}`,
}

// --- Tiny localStorage-backed store so job data survives navigation/refresh ---
const KEY = 'vidgen_job'

export const store = {
  save(job) {
    localStorage.setItem(KEY, JSON.stringify(job))
  },
  load() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || 'null')
    } catch (e) {
      return null
    }
  },
  update(patch) {
    const cur = store.load() || {}
    const next = { ...cur, ...patch }
    store.save(next)
    return next
  },
  clear() {
    localStorage.removeItem(KEY)
  },
}
