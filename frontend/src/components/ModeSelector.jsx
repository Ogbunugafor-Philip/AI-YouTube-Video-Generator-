export default function ModeSelector({ mode, onChange }) {
  return (
    <div className="mode-grid">
      <button
        type="button"
        className={`card mode-card ${mode === 'topic' ? 'selected' : ''}`}
        onClick={() => onChange('topic')}
      >
        <div className="icon">💡</div>
        <h3>Topic Mode</h3>
        <p>Give a topic and let the AI write the full narration script for you.</p>
      </button>

      <button
        type="button"
        className={`card mode-card ${mode === 'writeup' ? 'selected' : ''}`}
        onClick={() => onChange('writeup')}
      >
        <div className="icon">📝</div>
        <h3>Write-Up Mode</h3>
        <p>Paste your own script. We never change your words — only split scenes.</p>
      </button>
    </div>
  )
}
