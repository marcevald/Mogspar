import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'

export default function AuthPage() {
  const [tab, setTab] = useState('login')
  const [inviteRequired, setInviteRequired] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    api.auth.config().then(c => setInviteRequired(c.invite_required)).catch(() => {})
  }, [])

  return (
    <div className="screen justify-center" style={{ minHeight: '100dvh' }}>
      <div style={{ padding: '0 24px', width: '100%' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', padding: '48px 0 32px' }}>
          <span style={{ fontSize: 42, color: 'var(--text-primary)', display: 'block', marginBottom: 8 }}>♠</span>
          <h1 className="font-display" style={{ fontSize: 32, fontWeight: 500, letterSpacing: -0.5, color: 'var(--text-primary)' }}>Møgspar</h1>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 5 }}>The trick-taking game</p>
        </div>

        {/* Tab toggle */}
        <div className="tabs">
          <button className={`tab ${tab === 'login' ? 'on' : ''}`} onClick={() => setTab('login')}>Sign in</button>
          <button className={`tab ${tab === 'register' ? 'on' : ''}`} onClick={() => setTab('register')}>Register</button>
        </div>

        {tab === 'login'
          ? <LoginForm login={login} navigate={navigate} />
          : <RegisterForm login={login} navigate={navigate} inviteRequired={inviteRequired} />
        }
      </div>
    </div>
  )
}

function LoginForm({ login, navigate }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="fld">
        <label>Username</label>
        <input className="inp" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required />
      </div>
      <div className="fld">
        <label>Password</label>
        <input type="password" className="inp" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required />
      </div>
      {error && <p style={{ fontSize: 12, color: 'var(--red-text)', marginBottom: 10 }}>{error}</p>}
      <button type="submit" className="btnp" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
    </form>
  )
}

function RegisterForm({ login, navigate, inviteRequired }) {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    setError('')
    setLoading(true)
    try {
      await api.auth.register(username, email, password, inviteCode)
      // Auto-login with the same credentials — no security concern, just convenience
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="fld">
        <label>Username</label>
        <input className="inp" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" required />
      </div>
      <div className="fld">
        <label>Email</label>
        <input type="email" className="inp" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" required />
      </div>
      <div className="fld">
        <label>Password</label>
        <input
          type="password"
          className="inp"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="new-password"
          required
          style={password && password.length < 8 ? { borderColor: 'var(--red-text)' } : {}}
        />
        {password && password.length < 8 && (
          <p style={{ fontSize: 11, color: 'var(--red-text)', marginTop: 4 }}>At least 8 characters required</p>
        )}
      </div>
      <div className="fld">
        <label>Confirm password</label>
        <input
          type="password"
          className="inp"
          value={confirmPassword}
          onChange={e => setConfirmPassword(e.target.value)}
          autoComplete="new-password"
          required
          style={confirmPassword && confirmPassword !== password ? { borderColor: 'var(--red-text)' } : {}}
        />
        {confirmPassword && confirmPassword !== password && (
          <p style={{ fontSize: 11, color: 'var(--red-text)', marginTop: 4 }}>Passwords do not match</p>
        )}
      </div>
      {inviteRequired && (
        <div className="fld">
          <label>Invite code</label>
          <input className="inp" value={inviteCode} onChange={e => setInviteCode(e.target.value)} autoComplete="off" required />
        </div>
      )}
      {error && <p style={{ fontSize: 12, color: 'var(--red-text)', marginBottom: 10 }}>{error}</p>}
      <button type="submit" className="btnp" disabled={loading || password.length < 8 || (confirmPassword !== '' && confirmPassword !== password)}>
        {loading ? 'Creating account…' : 'Create account'}
      </button>
    </form>
  )
}
