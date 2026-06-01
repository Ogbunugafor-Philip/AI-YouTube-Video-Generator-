import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import ScriptReview from './pages/ScriptReview.jsx'
import Progress from './pages/Progress.jsx'
import Result from './pages/Result.jsx'
import Admin from './pages/Admin.jsx'

export default function App() {
  const location = useLocation()
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand">
          <span className="brand-mark">▶</span> AI Video Generator
        </Link>
        <nav className="nav">
          <Link className={location.pathname === '/' ? 'active' : ''} to="/">
            Create
          </Link>
          <Link className={location.pathname === '/admin' ? 'active' : ''} to="/admin">
            Admin
          </Link>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/review" element={<ScriptReview />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/result" element={<Result />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </main>

      <footer className="app-footer">
        <span>AI YouTube Video Generator · Phase 1</span>
      </footer>
    </div>
  )
}
