import { useState, useEffect } from 'react'
import { api } from '../api'
import Spinner from './Spinner'

export default function StatsView() {
  const [tab, setTab] = useState('leaderboard')
  const [variant, setVariant] = useState(null) // null = all variants

  return (
    <>
      <div className="tabs" style={{ marginBottom: 8 }}>
        <button className={`tab ${tab === 'leaderboard' ? 'on' : ''}`} onClick={() => setTab('leaderboard')}>Leaderboard</button>
        <button className={`tab ${tab === 'me' ? 'on' : ''}`} onClick={() => setTab('me')}>My stats</button>
      </div>
      <div className="tabs" style={{ marginBottom: 12 }}>
        <button className={`tab ${variant === null ? 'on' : ''}`} onClick={() => setVariant(null)}>All</button>
        <button className={`tab ${variant === 'mogspar' ? 'on' : ''}`} onClick={() => setVariant('mogspar')}>Møgspar</button>
        <button className={`tab ${variant === 'pirat_bridge' ? 'on' : ''}`} onClick={() => setVariant('pirat_bridge')}>Pirat Bridge</button>
      </div>
      {tab === 'leaderboard' ? <Leaderboard variant={variant} /> : <MyStats variant={variant} />}
    </>
  )
}

function Leaderboard({ variant }) {
  const [entries, setEntries] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setEntries(null)
    api.stats.leaderboard(variant)
      .then(setEntries)
      .catch(e => setError(e.message))
  }, [variant])

  if (error) return <p className="alt altw">{error}</p>
  if (!entries) return <Spinner />
  if (entries.length === 0) return (
    <div className="card" style={{ textAlign: 'center', padding: '32px 14px' }}>
      <div style={{ fontSize: 28, marginBottom: 8 }}>♠</div>
      <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No finished games yet.</p>
    </div>
  )

  return (
    <div className="csect">
      {entries.map((e, i) => (
        <div key={e.username} className="strow">
          <div className={`rnk ${i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : ''}`}>{i + 1}</div>
          <div className="av">{e.username[0].toUpperCase()}</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>
              {e.username}
              {!e.is_registered && <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginLeft: 6 }}>guest</span>}
            </div>
            <div className="txt-s">
              {e.games_played} game{e.games_played !== 1 ? 's' : ''}
              {e.games_won > 0 && ` · ${e.games_won} won`}
              {e.bid_accuracy >= 0 && ` · ${Math.round(e.bid_accuracy * 100)}% bid accuracy`}
            </div>
          </div>
          <div style={{
            fontFamily: 'Lora, serif',
            fontSize: 18,
            fontWeight: 500,
            color: e.total_score < 0 ? 'var(--red-text)' : i === 0 ? 'var(--amber)' : 'var(--text-primary)',
          }}>
            {e.total_score} pts
          </div>
        </div>
      ))}
    </div>
  )
}

function MyStats({ variant }) {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setStats(null)
    api.stats.me(variant)
      .then(setStats)
      .catch(e => setError(e.message))
  }, [variant])

  if (error) return <p className="alt altw">{error}</p>
  if (!stats) return <Spinner />

  const winRate = stats.games_played > 0
    ? Math.round((stats.games_won / stats.games_played) * 100)
    : null

  return (
    <>
      {/* Summary card */}
      <div className="mgrid" style={{ marginBottom: 12 }}>
        <StatCell label="Total score" value={`${stats.total_score} pts`} accent={stats.total_score < 0 ? 'var(--red-text)' : undefined} />
        <StatCell label="Games played" value={stats.games_played} />
        <StatCell label="Games won" value={stats.games_won} />
        {winRate !== null && <StatCell label="Win rate" value={`${winRate}%`} />}
        <StatCell label="Rounds played" value={stats.rounds_played} />
        {stats.bid_accuracy >= 0 && <StatCell label="Bid accuracy" value={`${Math.round(stats.bid_accuracy * 100)}%`} />}
      </div>

      {/* Game history */}
      {stats.recent_games.length > 0 && (
        <>
          <div className="slbl">Game history</div>
          <div className="csect">
            {stats.recent_games.map(g => {
              const date = new Date(g.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
              const statusBadge = g.status === 'finished'
                ? <span className="bdg bg">Finished</span>
                : g.status === 'active'
                ? <span className="bdg bl">● Live</span>
                : g.status === 'abandoned'
                ? <span className="bdg bo">Paused</span>
                : <span className="bdg bo">Lobby</span>

              return (
                <div key={g.code} className="prow" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="gccode">{g.code}</span>
                      {statusBadge}
                    </div>
                    <div className="txt-s" style={{ marginTop: 3 }}>
                      {date} · {g.num_players} players · {g.rounds_played} rounds
                      {g.status === 'finished' && ` · Rank #${g.rank}`}
                    </div>
                  </div>
                  <div style={{
                    fontFamily: 'Lora, serif',
                    fontSize: 17,
                    fontWeight: 500,
                    color: g.your_score < 0 ? 'var(--red-text)' : g.rank === 1 ? 'var(--amber)' : 'var(--text-primary)',
                  }}>
                    {g.your_score} pts
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {stats.recent_games.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: '32px 14px' }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>♠</div>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No games yet.</p>
        </div>
      )}
    </>
  )
}

function StatCell({ label, value, accent }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '14px 8px' }}>
      <div style={{
        fontFamily: 'Lora, serif',
        fontSize: 22,
        fontWeight: 500,
        color: accent ?? 'var(--text-primary)',
      }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 3 }}>{label}</div>
    </div>
  )
}
