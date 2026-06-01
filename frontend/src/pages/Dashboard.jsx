import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ModeSelector from '../components/ModeSelector.jsx'
import TopicForm from '../components/TopicForm.jsx'
import WriteUpForm from '../components/WriteUpForm.jsx'
import { api, store } from '../api.js'

export default function Dashboard() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('topic')
  const [topic, setTopic] = useState('')
  const [content, setContent] = useState('')
  const [duration, setDuration] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleGenerate() {
    setError('')
    if (mode === 'topic' && !topic.trim()) {
      setError('Please enter a topic.')
      return
    }
    if (mode === 'writeup' && !content.trim()) {
      setError('Please paste your write-up.')
      return
    }

    setLoading(true)
    try {
      const payload = {
        mode,
        duration_minutes: duration,
        topic: mode === 'topic' ? topic : null,
        content: mode === 'writeup' ? content : null,
      }
      const data = await api.generateScript(payload)
      store.save({
        job_id: data.job_id,
        title: data.title,
        script_text: data.script_text,
        scenes: data.scenes,
        duration_minutes: duration,
        mode,
      })
      navigate('/review')
    } catch (e) {
      setError(e.message || 'Failed to generate script.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="page-title">Create a new video</h1>
      <p className="subtitle">
        Pick a mode, describe your idea, and generate a YouTube-ready video.
      </p>

      {error && <div className="error">{error}</div>}

      <ModeSelector mode={mode} onChange={setMode} />

      {mode === 'topic' ? (
        <TopicForm
          topic={topic}
          duration={duration}
          onTopic={setTopic}
          onDuration={setDuration}
        />
      ) : (
        <WriteUpForm
          content={content}
          duration={duration}
          onContent={setContent}
          onDuration={setDuration}
        />
      )}

      <div className="actions">
        <button className="btn" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generating…' : 'Generate Script'}
        </button>
      </div>
    </div>
  )
}
