import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ProgressTracker from '../components/ProgressTracker.jsx'
import { api, store } from '../api.js'

export default function Progress() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [state, setState] = useState({
    percentage: 0,
    step: 'Starting…',
    total: 0,
    completed: 0,
  })
  const [error, setError] = useState('')
  const sourceRef = useRef(null)

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
    setState((s) => ({ ...s, total: j.scenes?.length || 0 }))

    // Real-time progress via Server-Sent Events (no polling).
    const es = new EventSource(api.progressUrl(j.job_id))
    sourceRef.current = es

    es.onmessage = (evt) => {
      let data
      try {
        data = JSON.parse(evt.data)
      } catch {
        return
      }
      setState((s) => ({
        percentage: data.percentage ?? s.percentage,
        step: data.step || s.step,
        total: data.scenes_total || s.total,
        completed: data.scenes_completed ?? s.completed,
      }))

      if (data.event === 'complete' || data.status === 'complete') {
        store.update({
          video_path: data.video_path,
          thumbnail_path: data.thumbnail_path,
        })
        es.close()
        navigate('/result')
      } else if (data.event === 'error' || data.status === 'error') {
        setError(data.step || 'Production failed.')
        es.close()
      }
    }

    es.onerror = () => {
      // The browser auto-reconnects; surface a soft note only if nothing arrived.
      setState((s) => {
        if (s.percentage === 0) {
          setError('Lost connection to progress stream. Retrying…')
        }
        return s
      })
    }

    return () => es.close()
  }, [navigate])

  if (!job) return null

  return (
    <div>
      <h1 className="page-title center">Producing your video</h1>
      <p className="subtitle center">{job.title}</p>

      {error && <div className="error">{error}</div>}

      <ProgressTracker
        percentage={state.percentage}
        step={state.step}
        total={state.total}
        completed={state.completed}
      />
    </div>
  )
}
