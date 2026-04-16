import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'
import Spinner from '../components/Spinner'
import StatsView from '../components/StatsView'

export default function HomePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [games, setGames] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [tab, setTab] = useState('home')

  useEffect(() => {
    const fetch = () => api.games.list().then(setGames).catch(() => {})
    fetch().finally(() => setLoading(false))
    let id = setInterval(fetch, 10000)

    function onVisibility() {
      clearInterval(id)
      if (document.visibilityState === 'visible') {
        fetch()
        id = setInterval(fetch, 10000)
      } else {
        id = setInterval(fetch, 60000)
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  const activeGames = games.filter(g => g.status === 'lobby' || g.status === 'active' || g.status === 'abandoned')
  const pastGames = games.filter(g => g.status === 'finished')

  async function handleCreate() {
    setCreating(true)
    try {
      const game = await api.games.create()
      navigate(`/game/${game.code}`)
    } catch {
      setCreating(false)
    }
  }

  const initial = user?.username?.[0]?.toUpperCase() ?? '?'

  return (
    <div className="screen">
      {/* Header */}
      <div className="ahead">
        <div>
          <div className="atitle">♠ Møgspar</div>
          <div className="asub">Good {greeting()}, {user?.username}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {tab === 'home' && (
            <button className="btns" style={{ width: 'auto' }} onClick={handleCreate} disabled={creating}>
              {creating ? '…' : '+ New game'}
            </button>
          )}
          <div className="av" style={{ cursor: 'pointer' }} onClick={() => setTab(tab === 'home' ? 'profile' : 'home')}>
            {initial}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="cont">
        {tab === 'home' && (
          <>

            {loading ? (
              <Spinner className="mt-8" />
            ) : (
              <>
                {activeGames.length > 0 && (
                  <>
                    <div className="slbl">Active games</div>
                    <div className="csect">
                      {activeGames.map(game => (
                        <GameCard key={game.id} game={game} onClick={() => navigate(`/game/${game.code}`)} />
                      ))}
                    </div>
                  </>
                )}

                {pastGames.length > 0 && (
                  <>
                    <div className="slbl">Past games</div>
                    <div className="csect">
                      {pastGames.map(game => (
                        <GameCard key={game.id} game={game} onClick={() => navigate(`/game/${game.code}`)} />
                      ))}
                    </div>
                  </>
                )}

                {games.length === 0 && (
                  <div className="card" style={{ textAlign: 'center', padding: '32px 14px' }}>
                    <div style={{ fontSize: 32, marginBottom: 8 }}>♠</div>
                    <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No games yet. Create one or join with a code.</p>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {tab === 'stats' && <StatsView />}

        {tab === 'profile' && (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div className="av" style={{ width: 48, height: 48, fontSize: 20 }}>{initial}</div>
              <div>
                <div style={{ fontWeight: 500 }}>{user?.username}</div>
                <div className="txt-s">{user?.email}</div>
              </div>
            </div>
            <button className="btns" style={{ width: '100%' }} onClick={logout}>Sign out</button>
          </div>
        )}
      </div>

      {/* Bottom nav */}
      <div className="bnav">
        <button className={`nit ${tab === 'home' ? 'on' : ''}`} onClick={() => setTab('home')}>
          <span className="nico">⌂</span>Home
        </button>
        <button className={`nit ${tab === 'stats' ? 'on' : ''}`} onClick={() => setTab('stats')}>
          <span className="nico">◉</span>Stats
        </button>
        <button className={`nit ${tab === 'profile' ? 'on' : ''}`} onClick={() => setTab('profile')}>
          <span className="nico">◯</span>Profile
        </button>
      </div>
    </div>
  )
}

function GameCard({ game, onClick }) {
  const badge = game.status === 'active'
    ? <span className="bdg bl">● Live</span>
    : game.status === 'lobby'
    ? <span className="bdg bo">Lobby</span>
    : game.status === 'abandoned'
    ? <span className="bdg bo">Paused</span>
    : <span className="bdg bg">Finished</span>

  const variantLabel = game.variant === 'pirat_bridge' ? 'Pirat Bridge' : 'Møgspar'

  return (
    <div className="prow" style={{ cursor: 'pointer', justifyContent: 'space-between' }} onClick={onClick}>
      <div>
        <div className="gccode">{game.code}</div>
        <div className="txt-s" style={{ marginTop: 3 }}>{game.players.length} players · {variantLabel}</div>
      </div>
      {badge}
    </div>
  )
}

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 18) return 'afternoon'
  return 'evening'
}
