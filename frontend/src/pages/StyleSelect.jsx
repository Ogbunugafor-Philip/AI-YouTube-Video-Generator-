import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, store } from '../api.js'

const ICONS = { cinematic: '🎬', minimalist: '⬜', corporate: '🏢', vibrant: '🌈' }

export default function StyleSelect() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [styles, setStyles] = useState([])
  const [selected, setSelected] = useState('cinematic')
  const [error, setError] = useState('')

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
    if (j.video_style) setSelected(j.video_style)
    api
      .getStyleOptions()
      .then((res) => setStyles(res.styles || []))
      .catch((e) => setError(e.message || 'Failed to load styles.'))
  }, [navigate])

  function handleContinue() {
    store.update({ video_style: selected })
    navigate('/voice')
  }

  if (!job) return null

  return (
    <div>
      <h1 className="page-title">Choose a video style</h1>
      <p className="subtitle">
        Step 1 of 3 · This look is applied to every generated scene.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="mode-grid">
        {styles.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`card mode-card ${selected === s.id ? 'selected' : ''}`}
            onClick={() => setSelected(s.id)}
          >
            <div className="icon">{ICONS[s.id] || '🎨'}</div>
            <h3>{s.name}</h3>
            <p>{s.description}</p>
          </button>
        ))}
      </div>

      <div className="actions">
        <button className="btn" onClick={handleContinue} disabled={!selected}>
          Continue →
        </button>
        <button className="btn ghost" onClick={() => navigate('/review')}>
          ← Back
        </button>
      </div>
    </div>
  )
}
