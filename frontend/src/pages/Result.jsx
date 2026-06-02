import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import VideoPlayer from '../components/VideoPlayer.jsx'
import ThumbnailPreview from '../components/ThumbnailPreview.jsx'
import { api, store } from '../api.js'

export default function Result() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [thumbBust, setThumbBust] = useState(0)
  const [regenerating, setRegenerating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [draftUrl, setDraftUrl] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
    setThumbBust(Date.now())
  }, [navigate])

  async function handleRegenThumb() {
    setError('')
    setRegenerating(true)
    try {
      await api.regenerateThumbnail(job.job_id, job.title)
      setThumbBust(Date.now()) // cache-bust the <img>
    } catch (e) {
      setError(e.message || 'Failed to regenerate thumbnail.')
    } finally {
      setRegenerating(false)
    }
  }

  async function handleUpload() {
    setError('')
    setNotice('')
    setUploading(true)
    try {
      const res = await api.uploadToYoutube(job.job_id)
      setDraftUrl(res.draft_url)
      setNotice('Uploaded to YouTube as a private draft. It will appear in History.')
    } catch (e) {
      setError(e.message || 'Failed to upload to YouTube.')
    } finally {
      setUploading(false)
    }
  }

  function handleNew() {
    store.clear()
    navigate('/')
  }

  if (!job) return null

  return (
    <div>
      <h1 className="page-title">🎉 {job.title}</h1>
      <p className="subtitle">Your video is ready.</p>

      {error && <div className="error">{error}</div>}
      {notice && (
        <div
          className="error"
          style={{ background: 'rgba(46,204,113,0.15)', borderColor: '#2ecc71', color: '#d6ffe6' }}
        >
          {notice}{' '}
          {draftUrl && (
            <a href={draftUrl} target="_blank" rel="noreferrer" style={{ color: '#d6ffe6', fontWeight: 700 }}>
              Open draft ↗
            </a>
          )}
        </div>
      )}

      <div className="result-grid">
        <VideoPlayer src={api.downloadUrl(job.job_id)} />
        <ThumbnailPreview src={api.thumbnailUrl(job.job_id, thumbBust)} title={job.title} />
      </div>

      <div className="actions">
        <a className="btn" href={api.downloadUrl(job.job_id)} download>
          ⬇ Download MP4
        </a>
        <button
          className="btn secondary"
          onClick={handleRegenThumb}
          disabled={regenerating}
        >
          {regenerating ? 'Regenerating…' : '↻ Regenerate Thumbnail'}
        </button>
        <button className="btn secondary" onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Uploading…' : '▶ Upload to YouTube'}
        </button>
        <button className="btn ghost" onClick={handleNew}>
          + Start New Video
        </button>
      </div>
    </div>
  )
}
