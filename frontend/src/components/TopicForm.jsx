export default function TopicForm({ topic, duration, onTopic, onDuration }) {
  return (
    <div className="card">
      <div className="field">
        <label htmlFor="topic">What should the video be about?</label>
        <input
          id="topic"
          type="text"
          placeholder="e.g. How AI is changing everyday life in Nigeria"
          value={topic}
          onChange={(e) => onTopic(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="duration-topic">Duration</label>
        <select
          id="duration-topic"
          value={duration}
          onChange={(e) => onDuration(Number(e.target.value))}
        >
          <option value={3}>3 minutes (~450 words)</option>
          <option value={4}>4 minutes (~600 words)</option>
          <option value={5}>5 minutes (~750 words)</option>
        </select>
      </div>
    </div>
  )
}
