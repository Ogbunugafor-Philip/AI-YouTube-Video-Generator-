import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Admin() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getStats()
      .then(setStats)
      .catch((e) => setError(e.message || 'Failed to load stats.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 className="page-title">Admin Dashboard</h1>
      <p className="subtitle">Production history and estimated costs.</p>

      {error && <div className="error">{error}</div>}
      {loading && <div className="spinner" />}

      {stats && (
        <>
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
                        <td className="muted">{v.date}</td>
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
