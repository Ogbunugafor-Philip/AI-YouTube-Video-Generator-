import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import ScriptReview from './pages/ScriptReview.jsx'
import StyleSelect from './pages/StyleSelect.jsx'
import VoiceSelect from './pages/VoiceSelect.jsx'
import SceneEditor from './pages/SceneEditor.jsx'
import Progress from './pages/Progress.jsx'
import Result from './pages/Result.jsx'
import Admin from './pages/Admin.jsx'
import History from './pages/History.jsx'

export default function App() {
  const location = useLocation()
  const isActive = (p) => (location.pathname === p ? 'active' : '')
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand">
          <span className="brand-mark">▶</span> AI Video Generator
        </Link>
        <nav className="nav">
          <Link className={isActive('/')} to="/">
            Create
          </Link>
          <Link className={isActive('/history')} to="/history">
            History
          </Link>
          <Link className={isActive('/admin')} to="/admin">
            Admin
          </Link>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<ScriptReview />} />
          <Route path="/style" element={<StyleSelect />} />
          <Route path="/voice" element={<VoiceSelect />} />
          <Route path="/scenes" element={<SceneEditor />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/result" element={<Result />} />
          <Route path="/history" element={<History />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </main>

      <footer className="app-footer">
        <span>AI YouTube Video Generator · Phase 3</span>
      </footer>
    </div>
  )
}
