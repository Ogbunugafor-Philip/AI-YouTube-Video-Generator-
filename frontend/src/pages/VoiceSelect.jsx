import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, store } from '../api.js'

export default function VoiceSelect() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [voices, setVoices] = useState([])
  const [selected, setSelected] = useState('')
  const [loadingId, setLoadingId] = useState('')
  const [playingId, setPlayingId] = useState('')
  const [error, setError] = useState('')
  const audioRef = useRef(null)

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
    api
      .getVoiceOptions()
      .then((res) => {
        setVoices(res.voices || [])
        setSelected(j.voice || res.default || (res.voices?.[0]?.id ?? ''))
      })
      .catch((e) => setError(e.message || 'Failed to load voices.'))
    return () => {
      if (audioRef.current) audioRef.current.pause()
    }
  }, [navigate])

  async function handlePreview(voiceId) {
    setError('')
    const el = audioRef.current
    if (!el) return
    if (playingId === voiceId) {
      el.pause()
      setPlayingId('')
      return
    }
    setLoadingId(voiceId)
    el.src = api.voicePreviewUrl(voiceId)
    try {
      await el.play()
      setPlayingId(voiceId)
    } catch (e) {
      setError('Could not play preview (the voice clip may still be generating).')
    } finally {
      setLoadingId('')
    }
  }

  function handleContinue() {
    store.update({ voice: selected })
    navigate('/scenes')
  }

  if (!job) return null

  return (
    <div>
      <h1 className="page-title">Choose a narration voice</h1>
      <p className="subtitle">
        Step 2 of 3 · Pick a voice and preview it. Defaults if you skip.
      </p>

      {error && <div className="error">{error}</div>}

      <audio ref={audioRef} onEnded={() => setPlayingId('')} hidden />

      <div className="voice-list">
        {voices.map((v) => (
          <div
            key={v.id}
            className={`card voice-card ${selected === v.id ? 'selected' : ''}`}
            onClick={() => setSelected(v.id)}
          >
            <div className="voice-info">
              <div className="voice-name">
                {selected === v.id ? '◉' : '○'} {v.name}
              </div>
              <div className="muted voice-desc">{v.description}</div>
            </div>
            <button
              type="button"
              className="btn ghost voice-preview-btn"
              onClick={(e) => {
                e.stopPropagation()
                handlePreview(v.id)
              }}
              disabled={loadingId === v.id}
            >
              {loadingId === v.id
                ? 'Loading…'
                : playingId === v.id
                ? '■ Stop'
                : '▶ Preview'}
            </button>
          </div>
        ))}
      </div>

      <div className="actions">
        <button className="btn" onClick={handleContinue} disabled={!selected}>
          Continue →
        </button>
        <button className="btn ghost" onClick={() => navigate('/style')}>
          ← Back
        </button>
      </div>
    </div>
  )
}
