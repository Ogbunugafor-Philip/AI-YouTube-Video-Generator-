import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SceneViewer from '../components/SceneViewer.jsx'
import { api, store } from '../api.js'

export default function ScriptReview() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
  }, [navigate])

  async function handleApprove() {
    setError('')
    setApproving(true)
    try {
      await api.approveScript(job.job_id)
      navigate('/progress')
    } catch (e) {
      setError(e.message || 'Failed to start production.')
      setApproving(false)
    }
  }

  if (!job) return null

  return (
    <div>
      <h1 className="page-title">{job.title}</h1>
      <p className="subtitle">
        Review the script and {job.scenes?.length || 0} scenes before producing.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="card" style={{ marginBottom: 22 }}>
        <h3>Full Script</h3>
        <div className="script-box">{job.script_text}</div>
      </div>

      <div className="card" style={{ marginBottom: 22 }}>
        <h3>Scenes ({job.scenes?.length || 0})</h3>
        <SceneViewer scenes={job.scenes} />
      </div>

      <div className="actions">
        <button className="btn" onClick={handleApprove} disabled={approving}>
          {approving ? 'Starting…' : '✓ Approve & Produce'}
        </button>
        <button
          className="btn secondary"
          onClick={() => navigate('/')}
          disabled={approving}
        >
          ↺ Regenerate
        </button>
      </div>
    </div>
  )
}
