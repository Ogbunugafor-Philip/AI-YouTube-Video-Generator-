export default function ProgressTracker({ percentage, step, total, completed }) {
  const boxes = Array.from({ length: total || 0 }, (_, i) => i + 1)
  return (
    <div className="progress-wrap">
      <div className="progress-pct">{Math.round(percentage)}%</div>
      <div className="progress-step">{step || 'Starting…'}</div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${percentage}%` }} />
      </div>

      {total > 0 && (
        <>
          <p className="muted">
            {completed} / {total} scenes rendered
          </p>
          <div className="scene-grid">
            {boxes.map((n) => (
              <div key={n} className={`scene-box ${n <= completed ? 'done' : ''}`}>
                {n <= completed ? '✓' : n}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
