import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SceneViewer from '../components/SceneViewer.jsx'
import { api, store } from '../api.js'

const WPM = 150
const countWords = (t) => (t || '').trim().split(/\s+/).filter(Boolean).length
const estMinutes = (t) => Math.max(1, Math.round(countWords(t) / WPM))

export default function ScriptReview() {
  const navigate = useNavigate()
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  const [approving, setApproving] = useState(false)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [showOriginal, setShowOriginal] = useState(false)
  const originalRef = useRef('') // AI-generated script captured on first load

  useEffect(() => {
    const j = store.load()
    if (!j || !j.job_id) {
      navigate('/')
      return
    }
    setJob(j)
    setDraft(j.script_text || '')
    originalRef.current = j.original_script_text || j.script_text || ''
  }, [navigate])

  const changed = useMemo(
    () => editing ? draft !== originalRef.current : (job?.script_text || '') !== originalRef.current,
    [editing, draft, job],
  )

  function handleDoneEditing() {
    // Recalculate duration from the edited word count and persist locally.
    const next = store.update({
      script_text: draft,
      duration_minutes: estMinutes(draft),
    })
    setJob(next)
    setEditing(false)
  }

  async function handleApprove() {
    setError('')
    setApproving(true)
    try {
      // Send the (possibly edited) script; backend re-splits scenes if changed.
      const res = await api.approveScript(job.job_id, job.script_text)
      const next = store.update({
        script_text: res.script_text,
        scenes: res.scenes,
        duration_minutes: res.duration_minutes,
        original_script_text: originalRef.current,
      })
      setJob(next)
      navigate('/style')
    } catch (e) {
      setError(e.message || 'Failed to approve script.')
      setApproving(false)
    }
  }

  if (!job) return null

  const liveText = editing ? draft : job.script_text
  const words = countWords(liveText)
  const minutes = editing ? estMinutes(draft) : job.duration_minutes

  return (
    <div>
      <h1 className="page-title">{job.title}</h1>
      <p className="subtitle">
        Review and edit the script, then continue to style &amp; voice.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="card" style={{ marginBottom: 22 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>Full Script</h3>
          <div className="row" style={{ gap: 8 }}>
            <span className="muted" style={{ alignSelf: 'center', fontSize: '0.85rem' }}>
              {words} words · ~{minutes} min
            </span>
            {!editing ? (
              <button className="btn ghost" onClick={() => { setDraft(job.script_text); setEditing(true) }}>
                ✎ Edit Script
              </button>
            ) : (
              <button className="btn" onClick={handleDoneEditing}>
                ✓ Done Editing
              </button>
            )}
            {changed && !editing && (
              <button className="btn ghost" onClick={() => setShowOriginal((s) => !s)}>
                {showOriginal ? 'Hide Original' : '⇄ Compare Original'}
              </button>
            )}
          </div>
        </div>

        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            style={{ marginTop: 14, minHeight: 320 }}
          />
        ) : (
          <div className="script-box" style={{ marginTop: 14 }}>{job.script_text}</div>
        )}

        {showOriginal && !editing && (
          <div style={{ marginTop: 16 }}>
            <div className="lbl muted" style={{ marginBottom: 6, fontSize: '0.8rem', textTransform: 'uppercase' }}>
              Original AI script
            </div>
            <div className="script-box" style={{ opacity: 0.85, borderLeft: '3px solid var(--muted)' }}>
              {originalRef.current}
            </div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: 22 }}>
        <h3>Scenes ({job.scenes?.length || 0})</h3>
        <p className="muted" style={{ marginTop: -4 }}>
          {changed
            ? 'Scenes will be re-divided from your edited script when you approve.'
            : 'You can fine-tune the visual descriptions in the Scene Editor next.'}
        </p>
        <SceneViewer scenes={job.scenes} />
      </div>

      <div className="actions">
        <button className="btn" onClick={handleApprove} disabled={approving || editing}>
          {approving ? 'Preparing…' : '✓ Approve & Continue'}
        </button>
        <button
          className="btn secondary"
          onClick={() => navigate('/')}
          disabled={approving}
        >
          ↺ Regenerate
        </button>
      </div>
      {editing && (
        <p className="muted" style={{ marginTop: 10 }}>
          Click “Done Editing” to lock in your changes before approving.
        </p>
      )}
    </div>
  )
}
