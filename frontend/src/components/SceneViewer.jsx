export default function SceneViewer({ scenes = [] }) {
  if (!scenes.length) {
    return <p className="muted">No scenes generated.</p>
  }
  return (
    <div className="scene-list">
      {scenes.map((scene) => (
        <div className="scene-item" key={scene.scene_number}>
          <div className="scene-num">Scene {scene.scene_number}</div>
          <div className="narration">{scene.narration_text}</div>
          <div className="visual">🎬 {scene.visual_description}</div>
        </div>
      ))}
    </div>
  )
}
