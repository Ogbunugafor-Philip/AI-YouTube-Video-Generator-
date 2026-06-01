export default function VideoPlayer({ src }) {
  return (
    <div className="card video-player">
      <h3>Final Video</h3>
      {src ? (
        <video controls preload="metadata" src={src}>
          Your browser does not support the video tag.
        </video>
      ) : (
        <p className="muted">Video not available.</p>
      )}
    </div>
  )
}
