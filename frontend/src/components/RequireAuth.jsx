import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Spinner from './Spinner'

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth()

  if (loading) return <Spinner className="min-h-screen" />
  if (!user) return <Navigate to="/login" replace />
  return children
}
