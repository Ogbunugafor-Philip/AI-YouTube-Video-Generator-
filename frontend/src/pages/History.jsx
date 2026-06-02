import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'

const MODE_LABELS = { topic: 'Topic', writeup: 'Write-Up', news: 'Breaking News' }
const fmtDate = (ts) => {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleDateString()
  } catch {
    return ts
  }
}
const fmtNum = (n) => (n == null ? '—' : Number(n).toLocaleString())
const fmtMins = (m) => (m == null ? '—' : `${Number(m).toLocaleString()} min`)
const fmtSecs = (s) => {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  const r = s % 60
  return m > 0 ? `${m}m ${r}s` : `${r}s`
}

export default function History() {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [mode, setMode] = useState('all')
  const [sort, setSort] = useState('date')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    api
      .getHistory()
      .then((res) => setVideos(res.videos || []))
      .catch((e) => setError(e.message || 'Failed to load history.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    let list = videos.slice()
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter((v) => (v.title || '').toLowerCase().includes(q))
    }
    if (mode !== 'all') list = list.filter((v) => (v.mode || 'topic') === mode)
    if (from) list = list.filter((v) => (v.date || '') >= from)
    if (to) list = list.filter((v) => (v.date || '') <= to + 'T23:59:59')
    list.sort((a, b) =>
      sort === 'views'
        ? (b.views || 0) - (a.views || 0)
        : (b.date || '').localeCompare(a.date || ''),
    )
    return list
  }, [videos, search, mode, sort, from, to])

  async function openDetail(jobId) {
    setDetailLoading(true)
    setDetail({ job_id: jobId })
    try {
      const d = await api.getHistoryDetail(jobId)
      setDetail(d)
    } catch (e) {
      setError(e.message || 'Failed to load video detail.')
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <div>
      <h1 className="page-title">Video History</h1>
      <p className="subtitle">Every video produced — with live YouTube performance.</p>

      {error && <div className="error">{error}</div>}

      {/* ---- Filter bar ---- */}
      <div className="card filter-bar">
        <input
          type="text"
          placeholder="Search by title…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="all">All modes</option>
          <option value="topic">Topic</option>
          <option value="writeup">Write-Up</option>
          <option value="news">Breaking News</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="date">Newest first</option>
          <option value="views">Most views</option>
        </select>
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} title="From date" />
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} title="To date" />
      </div>

      {loading && <div className="spinner" />}
      {!loading && filtered.length === 0 && (
        <p className="muted">No videos match your filters yet.</p>
      )}

      <div className="history-grid">
        {filtered.map((v) => (
          <div className="card history-card" key={v.job_id} onClick={() => openDetail(v.job_id)}>
            <div className="history-thumb">
              {v.thumbnail_url ? (
                <img src={v.thumbnail_url} alt={v.title} loading="lazy" />
              ) : (
                <div className="history-thumb-ph">No thumbnail</div>
              )}
              <span className="history-badge">{MODE_LABELS[v.mode] || 'Topic'}</span>
            </div>
            <div className="history-body">
              <div className="history-title">{v.title}</div>
              <div className="muted history-meta">
                {fmtDate(v.date)} · {v.duration_minutes} min
              </div>
              <div className="history-stats">
                <span title="Views">👁 {fmtNum(v.views)}</span>
                <span title="Likes">👍 {fmtNum(v.likes)}</span>
                <span title="Comments">💬 {fmtNum(v.comments)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ---- Detail modal ---- */}
      {detail && (
        <div className="modal-overlay" onClick={() => setDetail(null)}>
          <div className="modal card" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setDetail(null)}>
              ✕
            </button>
            {detailLoading ? (
              <div className="spinner" />
            ) : (
              <>
                <h2 style={{ marginBottom: 4 }}>{detail.title}</h2>
                <p className="muted">
                  {MODE_LABELS[detail.mode] || 'Topic'} · {fmtDate(detail.date)} ·{' '}
                  {detail.duration_minutes} min
                  {detail.video_style ? ` · ${detail.video_style}` : ''}
                </p>

                <div className="stat-cards" style={{ marginTop: 16 }}>
                  <div className="card stat-card">
                    <div className="num">{fmtNum(detail.views)}</div>
                    <div className="lbl">Views</div>
                  </div>
                  <div className="card stat-card">
                    <div className="num">{fmtNum(detail.likes)}</div>
                    <div className="lbl">Likes</div>
                  </div>
                  <div className="card stat-card">
                    <div className="num">{fmtNum(detail.comments)}</div>
                    <div className="lbl">Comments</div>
                  </div>
                </div>

                {/* Watch-time & retention (YouTube Analytics API) */}
                <div className="stat-cards" style={{ marginTop: 0 }}>
                  <div className="card stat-card">
                    <div className="num" style={{ fontSize: '1.7rem' }}>
                      {fmtMins(detail.watch_time_minutes)}
                    </div>
                    <div className="lbl">Watch Time</div>
                  </div>
                  <div className="card stat-card">
                    <div className="num" style={{ fontSize: '1.7rem' }}>
                      {fmtSecs(detail.avg_view_duration_sec)}
                    </div>
                    <div className="lbl">Avg View Duration</div>
                  </div>
                  <div className="card stat-card">
                    <div className="num" style={{ fontSize: '1.7rem' }}>
                      {detail.avg_view_percentage == null ? '—' : `${detail.avg_view_percentage}%`}
                    </div>
                    <div className="lbl">Avg Retention</div>
                  </div>
                </div>
                {detail.youtube_video_id && detail.watch_time_minutes == null && (
                  <p className="muted" style={{ fontSize: '0.82rem', marginTop: 4 }}>
                    Watch-time needs the YouTube Analytics scope — re-run the token
                    setup to enable it.
                  </p>
                )}

                {detail.youtube_url && (
                  <p style={{ marginTop: 8 }}>
                    <a href={detail.youtube_url} target="_blank" rel="noreferrer" className="muted">
                      ↗ Open on YouTube
                    </a>
                  </p>
                )}

                <h3 style={{ marginTop: 18 }}>Script</h3>
                <div className="script-box">{detail.script_text || '—'}</div>

                <h3 style={{ marginTop: 18 }}>Scenes ({detail.scenes?.length || 0})</h3>
                <div className="scene-list">
                  {(detail.scenes || []).map((s, i) => (
                    <div className="scene-item" key={i}>
                      <div className="scene-num">Scene {s.scene_number ?? i + 1}</div>
                      <div className="narration">{s.narration_text}</div>
                      <div className="visual">🎬 {s.visual_description}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
