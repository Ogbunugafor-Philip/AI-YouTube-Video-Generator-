import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'

function fmt(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString()
  } catch (e) {
    return ts
  }
}

const STATUS_COLORS = {
  pending: '#f1c40f',
  processing: '#3498db',
  completed: '#2ecc71',
  skipped: '#9aa3c0',
  error: '#e94560',
}

export default function Admin() {
  const [stats, setStats] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')

  const loadAll = useCallback(async () => {
    setError('')
    try {
      const [s, a] = await Promise.all([api.getStats(), api.getAlerts()])
      setStats(s)
      setAlerts(a.alerts || [])
    } catch (e) {
      setError(e.message || 'Failed to load admin data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  async function handleCheckNews() {
    setBusy('check')
    setNotice('')
    setError('')
    try {
      const res = await api.fetchLatestNews()
      setNotice(`News check complete — ${res.count} qualifying story(ies) found.`)
      await loadAll()
    } catch (e) {
      setError(e.message || 'News check failed.')
    } finally {
      setBusy('')
    }
  }

  async function handleTestAlert() {
    setBusy('test')
    setNotice('')
    setError('')
    try {
      const res = await api.sendTestAlert()
      setNotice(`Test alert sent to ${res.to}.`)
      await loadAll()
    } catch (e) {
      setError(e.message || 'Test alert failed.')
    } finally {
      setBusy('')
    }
  }

  return (
    <div>
      <h1 className="page-title">Admin Dashboard</h1>
      <p className="subtitle">Production history, costs, and news automation.</p>

      {error && <div className="error">{error}</div>}
      {notice && (
        <div
          className="error"
          style={{ background: 'rgba(46,204,113,0.15)', borderColor: '#2ecc71', color: '#d6ffe6' }}
        >
          {notice}
        </div>
      )}
      {loading && <div className="spinner" />}

      {stats && (
        <>
          {/* ---- Production stats ---- */}
          <div className="stat-cards">
            <div className="card stat-card">
              <div className="num">{stats.total_videos}</div>
              <div className="lbl">Total Videos</div>
            </div>
            <div className="card stat-card">
              <div className="num">{stats.total_api_calls}</div>
              <div className="lbl">Total API Calls</div>
            </div>
            <div className="card stat-card">
              <div className="num">${stats.estimated_total_cost.toFixed(2)}</div>
              <div className="lbl">Estimated Cost</div>
            </div>
          </div>

          {/* ---- News automation stats ---- */}
          <div className="stat-cards">
            <div className="card stat-card">
              <div className="num">{stats.news_alerts_sent}</div>
              <div className="lbl">Alerts Sent</div>
            </div>
            <div className="card stat-card">
              <div className="num">
                {stats.yes_replies} / {stats.no_replies}
              </div>
              <div className="lbl">YES / NO Replies</div>
            </div>
            <div className="card stat-card">
              <div className="num">{stats.auto_videos}</div>
              <div className="lbl">Auto-Produced</div>
            </div>
          </div>

          {/* ---- News Monitor ---- */}
          <div className="card" style={{ marginBottom: 28 }}>
            <h3>📰 News Monitor</h3>
            <div className="row" style={{ marginBottom: 16 }}>
              <div>
                <div className="lbl">Last news check</div>
                <div>{fmt(stats.last_news_check)}</div>
              </div>
              <div>
                <div className="lbl">Next news check</div>
                <div>{fmt(stats.next_news_check)}</div>
              </div>
            </div>

            <div className="actions" style={{ marginTop: 0 }}>
              <button className="btn" onClick={handleCheckNews} disabled={busy}>
                {busy === 'check' ? 'Checking…' : '🔄 Check News Now'}
              </button>
              <button
                className="btn secondary"
                onClick={handleTestAlert}
                disabled={busy}
              >
                {busy === 'test' ? 'Sending…' : '✉ Send Test Alert'}
              </button>
            </div>
          </div>

          {/* ---- Recent alerts ---- */}
          <div className="card" style={{ marginBottom: 28 }}>
            <h3>Recent Alerts</h3>
            {alerts.length === 0 ? (
              <p className="muted">No alerts yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Source</th>
                    <th>Viral</th>
                    <th>Status</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a) => (
                    <tr key={a.story_id}>
                      <td>{a.title}</td>
                      <td className="muted">{a.source || '—'}</td>
                      <td>{a.viral_score ?? '—'}</td>
                      <td>
                        <span
                          style={{
                            color: STATUS_COLORS[a.status] || '#eaeaf0',
                            fontWeight: 700,
                          }}
                        >
                          {a.status}
                        </span>
                      </td>
                      <td className="muted">{fmt(a.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* ---- Produced videos ---- */}
          <div className="card">
            <h3>Videos Produced</h3>
            {stats.videos.length === 0 ? (
              <p className="muted">No videos produced yet.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Date</th>
                    <th>Duration</th>
                    <th>Est. Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.videos
                    .slice()
                    .reverse()
                    .map((v, i) => (
                      <tr key={`${v.job_id}-${i}`}>
                        <td>{v.title}</td>
                        <td className="muted">{fmt(v.date)}</td>
                        <td>{v.duration_minutes} min</td>
                        <td>${Number(v.estimated_cost).toFixed(2)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}
