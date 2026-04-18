import { useState, useEffect, useMemo } from 'react'
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
      {tab === 'leaderboard' ? <ScopedLeaderboard variant={variant} /> : <MyStats variant={variant} />}
    </>
  )
}

// ---------------------------------------------------------------------------
// Scoped leaderboard
// ---------------------------------------------------------------------------

function ScopedLeaderboard({ variant }) {
  const [scope, setScope] = useState('all')        // 'all' | 'lineup' | 'custom' | 'game'
  const [match, setMatch] = useState('exact')      // for custom
  const [customPlayers, setCustomPlayers] = useState([])
  const [lineups, setLineups] = useState(null)
  const [lineupIdx, setLineupIdx] = useState(null)
  const [gameCode, setGameCode] = useState('')
  const [appliedGameCode, setAppliedGameCode] = useState('')

  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Reset lineups and selections when variant changes
  useEffect(() => {
    setLineups(null)
    setLineupIdx(null)
  }, [variant])

  // Fetch lineups when scope=lineup is selected
  useEffect(() => {
    if (scope !== 'lineup' || lineups !== null) return
    api.stats.lineups({ min_games: 2, variant: variant ?? undefined })
      .then(ls => { setLineups(ls); if (ls.length) setLineupIdx(0) })
      .catch(e => setError(e.message))
  }, [scope, lineups, variant])

  // Build the effective API params
  const params = useMemo(() => {
    if (scope === 'all') {
      return { scope: 'all', variant: variant ?? undefined }
    }
    if (scope === 'lineup') {
      if (!lineups || lineupIdx === null || !lineups[lineupIdx]) return null
      return {
        scope: 'players',
        match: 'exact',
        players: lineups[lineupIdx].players,
        variant: variant ?? undefined,
      }
    }
    if (scope === 'custom') {
      if (customPlayers.length < 1) return null
      return {
        scope: 'players',
        match,
        players: customPlayers,
        variant: variant ?? undefined,
      }
    }
    if (scope === 'game') {
      if (!appliedGameCode) return null
      return { scope: 'game', game_code: appliedGameCode, variant: variant ?? undefined }
    }
    return null
  }, [scope, match, customPlayers, lineups, lineupIdx, appliedGameCode, variant])

  // Fetch scoped stats
  useEffect(() => {
    if (!params) { setData(null); setError(''); return }
    setLoading(true); setError('')
    api.stats.scoped(params)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [params])

  return (
    <>
      {/* Scope picker */}
      <div className="tabs" style={{ marginBottom: 10 }}>
        <button className={`tab ${scope === 'all' ? 'on' : ''}`} onClick={() => setScope('all')}>All</button>
        <button className={`tab ${scope === 'lineup' ? 'on' : ''}`} onClick={() => setScope('lineup')}>Lineup</button>
        <button className={`tab ${scope === 'custom' ? 'on' : ''}`} onClick={() => setScope('custom')}>Custom</button>
        <button className={`tab ${scope === 'game' ? 'on' : ''}`} onClick={() => setScope('game')}>Game</button>
      </div>

      {/* Scope-specific controls */}
      {scope === 'lineup' && (
        <LineupPicker lineups={lineups} selectedIdx={lineupIdx} onSelect={setLineupIdx} />
      )}

      {scope === 'custom' && (
        <CustomScopeControls
          players={customPlayers}
          onChange={setCustomPlayers}
          match={match}
          onMatchChange={setMatch}
        />
      )}

      {scope === 'game' && (
        <GameCodeInput
          value={gameCode}
          onChange={setGameCode}
          onApply={() => setAppliedGameCode(gameCode.trim().toUpperCase())}
        />
      )}

      {/* Results */}
      {error && <p className="alt altw">{error}</p>}
      {loading && <Spinner />}
      {!loading && !error && params && data && <LeaderboardList data={data} />}
      {!loading && !error && !params && <ScopePrompt scope={scope} />}
    </>
  )
}

function ScopePrompt({ scope }) {
  const msg = scope === 'lineup' ? 'Pick a lineup above.'
    : scope === 'custom' ? 'Add at least one player above.'
    : scope === 'game' ? 'Enter a game code above.'
    : ''
  return (
    <div className="card" style={{ textAlign: 'center', padding: '24px 14px' }}>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{msg}</p>
    </div>
  )
}

function LeaderboardList({ data }) {
  const entries = data.players
  if (entries.length === 0) return (
    <div className="card" style={{ textAlign: 'center', padding: '32px 14px' }}>
      <div style={{ fontSize: 28, marginBottom: 8 }}>♠</div>
      <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>No matching games.</p>
    </div>
  )
  return (
    <>
      <div className="txt-s" style={{ marginBottom: 6 }}>
        {data.games_count} game{data.games_count !== 1 ? 's' : ''}
      </div>
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
    </>
  )
}

function LineupPicker({ lineups, selectedIdx, onSelect }) {
  if (lineups === null) return <Spinner />
  if (lineups.length === 0) return (
    <div className="card" style={{ textAlign: 'center', padding: '24px 14px', marginBottom: 10 }}>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
        No recurring lineups yet — play at least two games with the same players.
      </p>
    </div>
  )
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="slbl">Lineup</div>
      <div className="csect">
        {lineups.map((l, i) => (
          <button
            key={i}
            className={`brow ${selectedIdx === i ? 'active' : ''}`}
            style={{
              background: selectedIdx === i ? 'var(--accent-bg)' : undefined,
              width: '100%', textAlign: 'left', cursor: 'pointer',
            }}
            onClick={() => onSelect(i)}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{l.players.join(', ')}</div>
              <div className="txt-s">{l.games_count} games</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

function CustomScopeControls({ players, onChange, match, onMatchChange }) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])

  useEffect(() => {
    const q = query.trim()
    if (!q) { setOptions([]); return }
    const t = setTimeout(() => {
      api.players.search(q)
        .then(opts => setOptions(opts.filter(o => !players.includes(o.username))))
        .catch(() => setOptions([]))
    }, 200)
    return () => clearTimeout(t)
  }, [query, players])

  const add = (u) => {
    if (!players.includes(u)) onChange([...players, u])
    setQuery('')
    setOptions([])
  }
  const remove = (u) => onChange(players.filter(x => x !== u))

  return (
    <div style={{ marginBottom: 10 }}>
      <div className="slbl">Players</div>
      {players.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {players.map(u => (
            <span key={u} style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '4px 8px', borderRadius: 12,
              background: 'var(--accent-bg)', fontSize: 13,
            }}>
              {u}
              <button
                onClick={() => remove(u)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 0, fontSize: 14 }}
              >×</button>
            </span>
          ))}
        </div>
      )}

      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Add player..."
        style={{ width: '100%', padding: '8px 10px', fontSize: 14, boxSizing: 'border-box' }}
      />
      {options.length > 0 && (
        <div className="csect" style={{ marginTop: 4 }}>
          {options.map(o => (
            <button
              key={o.username}
              className="brow"
              style={{ width: '100%', textAlign: 'left', cursor: 'pointer' }}
              onClick={() => add(o.username)}
            >
              <div style={{ flex: 1, fontSize: 14 }}>
                {o.username}
                {!o.is_registered && <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginLeft: 6 }}>guest</span>}
              </div>
            </button>
          ))}
        </div>
      )}

      {players.length > 0 && (
        <div className="tabs" style={{ marginTop: 8 }}>
          <button className={`tab ${match === 'exact' ? 'on' : ''}`} onClick={() => onMatchChange('exact')}>
            Same players only
          </button>
          <button className={`tab ${match === 'superset' ? 'on' : ''}`} onClick={() => onMatchChange('superset')}>
            Includes these players
          </button>
        </div>
      )}
    </div>
  )
}

function GameCodeInput({ value, onChange, onApply }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="slbl">Game code</div>
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') onApply() }}
          placeholder="MØG-47"
          style={{ flex: 1, padding: '8px 10px', fontSize: 14, boxSizing: 'border-box' }}
        />
        <button className="btn" onClick={onApply}>Show</button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// My stats (unchanged)
// ---------------------------------------------------------------------------

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
      <div className="mgrid" style={{ marginBottom: 12 }}>
        <StatCell label="Total score" value={`${stats.total_score} pts`} accent={stats.total_score < 0 ? 'var(--red-text)' : undefined} />
        <StatCell label="Games played" value={stats.games_played} />
        <StatCell label="Games won" value={stats.games_won} />
        {winRate !== null && <StatCell label="Win rate" value={`${winRate}%`} />}
        <StatCell label="Rounds played" value={stats.rounds_played} />
        {stats.bid_accuracy >= 0 && <StatCell label="Bid accuracy" value={`${Math.round(stats.bid_accuracy * 100)}%`} />}
      </div>

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
