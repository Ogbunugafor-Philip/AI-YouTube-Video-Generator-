export default function ThumbnailPreview({ src, title }) {
  return (
    <div className="card thumb-preview">
      <h3>Thumbnail</h3>
      {src ? (
        <img src={src} alt={title || 'Video thumbnail'} />
      ) : (
        <p className="muted">Thumbnail not available.</p>
      )}
    </div>
  )
}
