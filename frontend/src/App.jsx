import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import AuthPage from './pages/AuthPage'
import HomePage from './pages/HomePage'
import GamePage from './pages/GamePage'
import Spinner from './components/Spinner'
import useWakeLock from './hooks/useWakeLock'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner className="min-h-screen" />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RedirectIfAuthed({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner className="min-h-screen" />
  if (user) return <Navigate to="/" replace />
  return children
}

function WakeLockWhileAuthed() {
  const { user } = useAuth()
  useWakeLock(Boolean(user))
  return null
}

export default function App() {
  return (
    <>
      <WakeLockWhileAuthed />
      <Routes>
        <Route path="/login" element={<RedirectIfAuthed><AuthPage /></RedirectIfAuthed>} />
        <Route path="/" element={<RequireAuth><HomePage /></RequireAuth>} />
        <Route path="/game/:code" element={<RequireAuth><GamePage /></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
