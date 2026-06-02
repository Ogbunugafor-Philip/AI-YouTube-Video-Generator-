import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, store } from '../api.js'

export default function SceneEditor() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [scenes, setScenes] = useState([])
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
    setScenes((j.scenes || []).map((s) => ({ ...s })))
  }, [navigate])

  function updateVisual(idx, value) {
    setScenes((prev) => prev.map((s, i) => (i === idx ? { ...s, visual_description: value } : s)))
  }

  async function handleProceed() {
    setError('')
    setStarting(true)
    try {
      store.update({ scenes })
      await api.produce({
        job_id: job.job_id,
        scenes,
        voice: job.voice || null,
        video_style: job.video_style || null,
      })
      navigate('/progress')
    } catch (e) {
      setError(e.message || 'Failed to start generation.')
      setStarting(false)
    }
  }

  if (!job) return null

  return (
    <div>
      <h1 className="page-title">Scene editor</h1>
      <p className="subtitle">
        Step 3 of 3 · {scenes.length} scenes. Optionally tweak any visual description —
        editing is optional.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="scene-edit-list">
        {scenes.map((s, idx) => (
          <div className="scene-item scene-edit-item" key={s.scene_number ?? idx}>
            <div className="scene-num">Scene {s.scene_number ?? idx + 1}</div>
            <div className="narration">{s.narration_text}</div>
            <label className="visual-label">🎬 Visual description (sent to fal.ai)</label>
            <textarea
              className="visual-edit"
              value={s.visual_description}
              onChange={(e) => updateVisual(idx, e.target.value)}
            />
          </div>
        ))}
      </div>

      <div className="actions">
        <button className="btn" onClick={handleProceed} disabled={starting}>
          {starting ? 'Starting…' : '▶ Proceed to Generation'}
        </button>
        <button className="btn ghost" onClick={() => navigate('/voice')} disabled={starting}>
          ← Back
        </button>
      </div>
    </div>
  )
}
