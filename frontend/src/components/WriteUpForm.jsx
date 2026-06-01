export default function WriteUpForm({ content, duration, onContent, onDuration }) {
  return (
    <div className="card">
      <div className="field">
        <label htmlFor="content">Paste your script / write-up</label>
        <textarea
          id="content"
          placeholder="Paste your full narration here. Your words will be used exactly as written."
          value={content}
          onChange={(e) => onContent(e.target.value)}
        />
        <p className="muted" style={{ marginTop: 8, fontSize: '0.85rem' }}>
          Your content is never rewritten — it is only split into scenes.
        </p>
      </div>
      <div className="field">
        <label htmlFor="duration-writeup">Target duration</label>
        <select
          id="duration-writeup"
          value={duration}
          onChange={(e) => onDuration(Number(e.target.value))}
        >
          <option value={3}>3 minutes</option>
          <option value={4}>4 minutes</option>
          <option value={5}>5 minutes</option>
        </select>
      </div>
    </div>
  )
}
