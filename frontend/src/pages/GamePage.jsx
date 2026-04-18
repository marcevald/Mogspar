import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'
import Spinner from '../components/Spinner'
import StepperRow from '../components/StepperRow'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function maxCards(numPlayers, game) {
  return game?.max_cards_override ?? Math.floor(52 / numPlayers)
}

function cardsForRound(roundNumber, numPlayers, game) {
  const max = maxCards(numPlayers, game)
  if (game?.variant === 'pirat_bridge') {
    // Pirat Bridge: 1 → max → 1
    if (roundNumber <= max) return roundNumber
    return 2 * max - roundNumber + 1
  }
  // Møgspar (default): max → 1 → max
  if (roundNumber <= max) return max - roundNumber + 1
  return roundNumber - max
}

function totalRounds(numPlayers, game) {
  return 2 * maxCards(numPlayers, game)
}

function biddingOrder(firstSeat, numPlayers) {
  return Array.from({ length: numPlayers }, (_, i) => (firstSeat + i) % numPlayers)
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function GamePage() {
  const { code } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [game, setGame] = useState(null)
  const [activeRound, setActiveRound] = useState(null)
  const [scoreboard, setScoreboard] = useState(null)
  const [tab, setTab] = useState('round')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const g = await api.games.get(code)
      setGame(g)

      if (g.status !== 'lobby') {
        const sb = await api.games.scoreboard(code)
        setScoreboard(sb)

        const completedRounds = sb.scores.length > 0
          ? Math.max(...sb.scores.map(s => s.rounds_played))
          : 0

        // Find active round (first in-progress after all completed rounds)
        try {
          const r = await api.rounds.get(code, completedRounds + 1)
          setActiveRound(r.status !== 'finished' ? r : null)
        } catch (e) {
          if (e.status === 404) setActiveRound(null)
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [code])

  useEffect(() => {
    refresh()
    let id = setInterval(refresh, 2500)

    function onVisibility() {
      clearInterval(id)
      if (document.visibilityState === 'visible') {
        refresh() // immediate catch-up when tab becomes visible again
        id = setInterval(refresh, 2500)
      } else {
        id = setInterval(refresh, 30000)
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [refresh])

  if (loading) return <Spinner className="min-h-screen" />
  if (error) return (
    <div className="screen" style={{ justifyContent: 'center', alignItems: 'center', gap: 12, padding: 24 }}>
      <p style={{ color: 'var(--red-text)', textAlign: 'center' }}>{error}</p>
      <button className="btns" onClick={() => navigate('/')}>← Back home</button>
    </div>
  )
  if (!game) return null

  const isGM = game.game_master_id === user?.id
  const numPlayers = game.players.length

  return (
    <div className="screen">
      <GameHeader game={game} activeRound={activeRound} navigate={navigate} />

      <div className="cont" style={{ padding: game.status === 'lobby' ? 14 : 14 }}>
        {tab === 'round' && (
          game.status === 'lobby'
            ? <LobbyView game={game} isGM={isGM} refresh={refresh} navigate={navigate} />
            : game.status === 'finished'
            ? <GameOverView scoreboard={scoreboard} />
            : game.status === 'abandoned'
            ? <AbandonedView scoreboard={scoreboard} />
            : <RoundTab
                game={game}
                activeRound={activeRound}
                scoreboard={scoreboard}
                isGM={isGM}
                numPlayers={numPlayers}
                refresh={refresh}
                user={user}
              />
        )}
        {tab === 'scores' && (
          <ScoresTab scoreboard={scoreboard} game={game} activeRound={activeRound} />
        )}
        {tab === 'info' && (
          <GameInfoTab game={game} user={user} isGM={isGM} refresh={refresh} navigate={navigate} />
        )}
      </div>

      {game.status !== 'lobby' && game.status !== 'abandoned' && (
        <div className="bnav">
          <button className={`nit ${tab === 'round' ? 'on' : ''}`} onClick={() => setTab('round')}>
            <span className="nico">▶</span>Round
          </button>
          <button className={`nit ${tab === 'scores' ? 'on' : ''}`} onClick={() => setTab('scores')}>
            <span className="nico">◉</span>Scores
          </button>
          <button className={`nit ${tab === 'info' ? 'on' : ''}`} onClick={() => setTab('info')}>
            <span className="nico">ℹ</span>Game
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function GameHeader({ game, activeRound, navigate }) {
  const badge = game.status === 'active'
    ? <span className="bdg bl">● Live</span>
    : game.status === 'lobby'
    ? <span className="bdg bo">Lobby</span>
    : game.status === 'abandoned'
    ? <span className="bdg bo">Paused</span>
    : <span className="bdg bg">Finished</span>

  const title = game.status === 'lobby' ? 'Game lobby'
    : game.status === 'finished' ? 'Game over'
    : game.status === 'abandoned' ? 'Game paused'
    : activeRound ? `Round ${activeRound.round_number}` : 'Between rounds'

  return (
    <div className="ahead">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button className="btns" style={{ width: 'auto', padding: '6px 10px', fontSize: 16 }} onClick={() => navigate('/')}>←</button>
        <div>
          <div className="atitle">{title}</div>
          <div className="asub">{game.code}</div>
        </div>
      </div>
      {badge}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Lobby
// ---------------------------------------------------------------------------

function LobbyView({ game, isGM, refresh, navigate }) {
  const [order, setOrder] = useState(() =>
    [...game.players].sort((a, b) => a.seat_index - b.seat_index).map(p => p.username)
  )
  const [dealerUsername, setDealerUsername] = useState(null)
  const absoluteMax = Math.floor(52 / Math.max(game.players.length, 1))
  const [userSet, setUserSet] = useState(game.max_cards_override != null)
  const [customMax, setCustomMax] = useState(() => game.max_cards_override ?? absoluteMax)
  const [variant, setVariant] = useState(game.variant ?? 'mogspar')
  const [starting, setStarting] = useState(false)
  const [err, setErr] = useState('')

  // Search state (GM only)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [addingPlayer, setAddingPlayer] = useState(null)

  useEffect(() => {
    if (!userSet) setCustomMax(absoluteMax)
    else if (customMax > absoluteMax) setCustomMax(absoluteMax)
  }, [absoluteMax])

  // Sync newly joined players to end of local order
  useEffect(() => {
    setOrder(prev => {
      const existing = new Set(prev)
      const newOnes = game.players.filter(p => !existing.has(p.username)).map(p => p.username)
      return newOnes.length ? [...prev, ...newOnes] : prev
    })
  }, [game.players.length])

  // Debounced player search
  useEffect(() => {
    if (!isGM || searchQuery.length < 1) { setSearchResults([]); return }
    setSearching(true)
    const timer = setTimeout(async () => {
      try { setSearchResults(await api.players.search(searchQuery)) }
      finally { setSearching(false) }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery, isGM])

  function move(i, dir) {
    const j = i + dir
    if (j < 0 || j >= order.length) return
    setOrder(o => { const a = [...o]; [a[i], a[j]] = [a[j], a[i]]; return a })
  }

  async function handleAddPlayer(username) {
    setAddingPlayer(username)
    setErr('')
    try {
      await api.games.addPlayer(game.code, username)
      setSearchQuery('')
      setSearchResults([])
      await refresh()
    } catch (e) {
      setErr(e.message)
    } finally {
      setAddingPlayer(null)
    }
  }

  async function handleRemovePlayer(player_id, username) {
    setOrder(o => o.filter(u => u !== username))
    setErr('')
    try {
      await api.games.removePlayer(game.code, player_id)
      await refresh()
    } catch (e) {
      setErr(e.message)
      await refresh() // re-sync on failure
    }
  }

  async function handleStart() {
    if (!dealerUsername) { setErr('Select a dealer before starting.'); return }
    setErr('')
    setStarting(true)
    try {
      await api.games.reorder(game.code, order)
      await api.games.setDealer(game.code, dealerUsername)
      const defaultMax = Math.floor(52 / order.length)
      if (customMax !== defaultMax) await api.games.setMaxCards(game.code, customMax)
      await api.games.setVariant(game.code, variant)
      await api.games.start(game.code)
      await refresh()
    } catch (e) {
      setErr(e.message)
      setStarting(false)
    }
  }

  const inGameUsernames = new Set(game.players.map(p => p.username))
  const trimmed = searchQuery.trim()
  const exactMatch = searchResults.some(r => r.username.toLowerCase() === trimmed.toLowerCase())
  const showAddNew = trimmed.length >= 2 && !exactMatch && !searching

  return (
    <>
      {/* Game code — shown for identification only */}
      <div className="cblk">
        <div className="clbl">Game code</div>
        <div className="cval">{game.code}</div>
      </div>

      {/* Variant + Max cards (GM only) */}
      {isGM && (
        <>
          <div className="cblk" style={{ marginTop: 10 }}>
            <div className="clbl">Game variant</div>
            <div className="tabs" style={{ marginTop: 8 }}>
              <button className={`tab ${variant === 'mogspar' ? 'on' : ''}`} onClick={() => setVariant('mogspar')}>Møgspar</button>
              <button className={`tab ${variant === 'pirat_bridge' ? 'on' : ''}`} onClick={() => setVariant('pirat_bridge')}>Pirat Bridge</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
              {variant === 'pirat_bridge'
                ? `Pirat Bridge: ${customMax}→1→${customMax} · Correct: 10+2×tricks, wrong: −2`
                : `Møgspar: ${customMax}→1→${customMax} · Correct: 10+bid, wrong: −|diff|`}
            </div>
          </div>

          <div className="cblk" style={{ marginTop: 10 }}>
            <div className="clbl">Max cards per player</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
              <div className="stpr">
                <button className="sbtn" onClick={() => { setUserSet(true); setCustomMax(v => Math.max(1, v - 1)) }} disabled={customMax <= 1}>−</button>
                <span className="sval">{customMax}</span>
                <button className="sbtn" onClick={() => { setUserSet(true); setCustomMax(v => Math.min(absoluteMax, v + 1)) }} disabled={customMax >= absoluteMax}>+</button>
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {customMax === absoluteMax ? `default (${absoluteMax})` : `default is ${absoluteMax}`}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
              {variant === 'pirat_bridge'
                ? `${2 * customMax} rounds: 1→${customMax}→1`
                : `${2 * customMax} rounds: ${customMax}→1→${customMax}`}
            </div>
          </div>
        </>
      )}

      {/* Player search (GM only) */}
      {isGM && game.players.length < 26 && (
        <>
          <div className="slbl" style={{ marginTop: 12 }}>Add players</div>
          <div className="card" style={{ padding: '10px 12px' }}>
            <input
              className="inp"
              placeholder="Search by name…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              autoComplete="off"
              autoCorrect="off"
            />
            {searching && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>Searching…</div>}
            {searchResults.length > 0 && (
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {searchResults.map(player => {
                  const alreadyIn = inGameUsernames.has(player.username)
                  return (
                    <div key={player.id} className="prow" style={{ padding: '6px 0' }}>
                      <div style={{ flex: 1, fontSize: 14 }}>
                        {player.username}
                        {player.is_registered
                          ? <span className="bdg bl" style={{ marginLeft: 6, fontSize: 10 }}>Account</span>
                          : <span className="bdg" style={{ marginLeft: 6, fontSize: 10, color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>Guest</span>
                        }
                      </div>
                      {alreadyIn
                        ? <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Added</span>
                        : <button className="btns" style={{ padding: '4px 12px', fontSize: 12 }}
                            onClick={() => handleAddPlayer(player.username)}
                            disabled={addingPlayer === player.username}>
                            {addingPlayer === player.username ? '…' : 'Add'}
                          </button>
                      }
                    </div>
                  )
                })}
              </div>
            )}
            {showAddNew && (
              <button className="btns" style={{ marginTop: 8, width: '100%' }}
                onClick={() => handleAddPlayer(trimmed)}
                disabled={addingPlayer === trimmed}>
                {addingPlayer === trimmed ? 'Adding…' : `+ Add "${trimmed}" as new player`}
              </button>
            )}
          </div>
        </>
      )}

      {/* Player list */}
      <div className="slbl" style={{ marginTop: 12 }}>
        Players ({game.players.length} of 26)
        {isGM && <span style={{ fontSize: 11, color: 'var(--text-secondary)', marginLeft: 6 }}>↑↓ order · ☆ dealer · ✕ remove</span>}
      </div>
      <div className="csect">
        {order.map((username, i) => {
          const playerObj = game.players.find(p => p.username === username)
          const isDealer = username === dealerUsername
          const isGMPlayer = username === game.game_master_username
          return (
            <div key={username} className="prow">
              <div className="seat">{i + 1}</div>
              <div style={{ flex: 1, fontSize: 14 }}>
                {username}
                {playerObj && !playerObj.is_registered && (
                  <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginLeft: 6 }}>guest</span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {isDealer && <span className="bdg bo">🂠</span>}
                {isGMPlayer && <span className="bdg bo" style={{ fontSize: 10 }}>GM</span>}
                {isGM && (
                  <>
                    <button className="sbtn" style={{ fontSize: 12 }}
                      onClick={() => setDealerUsername(isDealer ? null : username)}>
                      {isDealer ? '★' : '☆'}
                    </button>
                    <button className="sbtn" style={{ fontSize: 12 }} onClick={() => move(i, -1)} disabled={i === 0}>↑</button>
                    <button className="sbtn" style={{ fontSize: 12 }} onClick={() => move(i, 1)} disabled={i === order.length - 1}>↓</button>
                    {!isGMPlayer && playerObj && (
                      <button className="sbtn" style={{ fontSize: 11, color: 'var(--red-text)' }}
                        onClick={() => handleRemovePlayer(playerObj.player_id, username)}>✕</button>
                    )}
                  </>
                )}
              </div>
            </div>
          )
        })}
        {game.players.length < 2 && (
          <div className="prow">
            <div className="seat empty">{game.players.length + 1}</div>
            <div style={{ flex: 1, fontSize: 13, color: 'var(--text-secondary)' }}>
              {isGM ? 'Search above to add players…' : 'Waiting for players…'}
            </div>
          </div>
        )}
      </div>

      {err && <p className="alt altw">{err}</p>}

      {isGM ? (
        <button className="btnam" onClick={handleStart} disabled={starting || game.players.length < 2}>
          {starting ? 'Starting…' : '▶ Start game'}
        </button>
      ) : (
        <div className="alt alti">Waiting for the game master to start the game.</div>
      )}

      {isGM && (
        <button className="btns"
          style={{ width: '100%', marginTop: 8, color: 'var(--red-text)', borderColor: 'var(--red-text)' }}
          onClick={async () => {
            if (!confirm('Permanently delete this game? This cannot be undone.')) return
            try { await api.games.delete(game.code); navigate('/') }
            catch (e) { setErr(e.message) }
          }}>
          Delete game
        </button>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Abandoned view
// ---------------------------------------------------------------------------

function AbandonedView({ scoreboard }) {
  if (!scoreboard) return <Spinner />
  const sorted = [...scoreboard.scores].sort((a, b) => b.total_score - a.total_score)
  return (
    <>
      <div className="alt altw">This game was ended early. The game master can resume it from the Game tab.</div>
      <div className="slbl">Scores so far</div>
      <div className="csect">
        {sorted.map((s, i) => (
          <div key={s.username} className="strow">
            <div className={`rnk ${i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : ''}`}>{i + 1}</div>
            <div className="av">{s.username[0].toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{s.username}</div>
              <div className="txt-s">{s.rounds_played} rounds played</div>
            </div>
            <div style={{
              fontFamily: 'Lora, serif',
              fontSize: 18,
              fontWeight: 500,
              color: s.total_score < 0 ? 'var(--red-text)' : i === 0 ? 'var(--amber)' : 'var(--text-primary)',
            }}>
              {s.total_score} pts
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Round tab dispatcher
// ---------------------------------------------------------------------------

function RoundTab({ game, activeRound, scoreboard, isGM, numPlayers, refresh, user }) {
  const completedRounds = scoreboard?.scores?.length > 0
    ? Math.max(...scoreboard.scores.map(s => s.rounds_played))
    : 0
  const nextRoundNum = completedRounds + 1
  const nextCards = cardsForRound(nextRoundNum, numPlayers, game)
  const total = totalRounds(numPlayers, game)

  if (!activeRound) {
    // Between rounds or game not started yet
    if (isGM) {
      return (
        <StartRoundView
          game={game}
          roundNum={nextRoundNum}
          cards={nextCards}
          total={total}
          refresh={refresh}
        />
      )
    }
    return (
      <div className="card" style={{ textAlign: 'center', padding: '32px 14px' }}>
        <div style={{ fontSize: 28, marginBottom: 8 }}>⏳</div>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
          Waiting for the game master to start round {nextRoundNum}…
        </p>
      </div>
    )
  }

  if (activeRound.status === 'bidding') {
    return isGM
      ? <BiddingGMView game={game} round={activeRound} numPlayers={numPlayers} refresh={refresh} />
      : <BiddingPlayerView game={game} round={activeRound} user={user} numPlayers={numPlayers} />
  }

  if (activeRound.status === 'playing') {
    return isGM
      ? <TrickEntryView game={game} round={activeRound} refresh={refresh} />
      : <PlayingPlayerView round={activeRound} game={game} scoreboard={scoreboard} />
  }

  return null
}

// ---------------------------------------------------------------------------
// Start round (GM)
// ---------------------------------------------------------------------------

function StartRoundView({ game, roundNum, cards, total, refresh }) {
  const [starting, setStarting] = useState(false)
  const [err, setErr] = useState('')

  async function handleStart() {
    setErr('')
    setStarting(true)
    try {
      await api.rounds.create(game.code, cards)
      await refresh()
    } catch (e) {
      setErr(e.message)
      setStarting(false)
    }
  }

  if (roundNum > total) {
    return (
      <FinishGameView game={game} refresh={refresh} />
    )
  }

  return (
    <>
      <div className="rbar">
        <div>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 17, fontWeight: 500 }}>
            Round {roundNum} of {total}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            {cards} card{cards !== 1 ? 's' : ''} per player · ♠ beats all suits
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 20, fontWeight: 500, color: 'var(--amber)' }}>
            {cards}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>cards</div>
        </div>
      </div>
      {err && <p className="alt altw">{err}</p>}
      <button className="btnam" onClick={handleStart} disabled={starting}>
        {starting ? 'Starting…' : `▶ Start round ${roundNum}`}
      </button>
    </>
  )
}

// ---------------------------------------------------------------------------
// Finish game (GM)
// ---------------------------------------------------------------------------

function FinishGameView({ game, refresh }) {
  const [finishing, setFinishing] = useState(false)
  const [err, setErr] = useState('')

  async function handleFinish() {
    setErr('')
    setFinishing(true)
    try {
      await api.games.finish(game.code)
      await refresh()
    } catch (e) {
      setErr(e.message)
      setFinishing(false)
    }
  }

  return (
    <>
      <div className="alto alt">All rounds complete! Finish the game to lock in the final scores.</div>
      {err && <p className="alt altw">{err}</p>}
      <button className="btnam" onClick={handleFinish} disabled={finishing}>
        {finishing ? 'Finishing…' : '🏆 Finish game'}
      </button>
    </>
  )
}

// ---------------------------------------------------------------------------
// Game over
// ---------------------------------------------------------------------------

function GameOverView({ scoreboard }) {
  if (!scoreboard) return <Spinner />
  const sorted = [...scoreboard.scores].sort((a, b) => b.total_score - a.total_score)

  return (
    <>
      <div className="alto alt">Game finished! Final standings:</div>
      <div className="csect">
        {sorted.map((s, i) => (
          <div key={s.username} className="strow">
            <div className={`rnk ${i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : ''}`}>
              {i + 1}
            </div>
            <div className="av">{s.username[0].toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{s.username}</div>
              <div className="txt-s">{s.rounds_played} rounds</div>
            </div>
            <div style={{
              fontFamily: 'Lora, serif',
              fontSize: 18,
              fontWeight: 500,
              color: s.total_score < 0 ? 'var(--red-text)' : i === 0 ? 'var(--amber)' : 'var(--text-primary)',
            }}>
              {s.total_score} pts
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Bidding — GM view
// ---------------------------------------------------------------------------

function BiddingGMView({ game, round, numPlayers, refresh }) {
  const order = biddingOrder(round.first_player_seat, numPlayers)
  const bidsBySeat = Object.fromEntries(round.bids.map(b => [b.seat_index, b.bid]))
  const playerBySeat = Object.fromEntries(game.players.map(p => [p.seat_index, p]))

  // Position of the most-recently-confirmed bid in bidding order — that's the
  // only confirmed row the GM may tap to re-edit (backend enforces the same rule).
  const confirmedPositions = order
    .map((seat, i) => (bidsBySeat[seat] !== undefined ? i : -1))
    .filter(i => i >= 0)
  const lastConfirmedPos = confirmedPositions.length ? Math.max(...confirmedPositions) : -1
  const lastConfirmedSeat = lastConfirmedPos >= 0 ? order[lastConfirmedPos] : null

  const nextSeat = order.find(s => bidsBySeat[s] === undefined) ?? null
  const bidsSubmitted = round.bids.length

  const sumSoFar = Object.values(bidsBySeat).reduce((a, b) => a + b, 0)
  const isLastBidder = bidsSubmitted === numPlayers - 1
  const forbiddenBidForNext = round.cards_per_player - sumSoFar

  const [editingSeat, setEditingSeat] = useState(null)
  const activeSeat = editingSeat ?? nextSeat
  const isEditing = editingSeat !== null
  const activePlayer = activeSeat !== null ? playerBySeat[activeSeat] : null

  // Default stepper value: pre-fill edits with the existing bid; otherwise suggest average.
  const [bidVal, setBidVal] = useState(() => {
    const remaining = round.cards_per_player - sumSoFar
    const remainingBidders = numPlayers - bidsSubmitted
    const avg = Math.max(0, Math.floor(remaining / Math.max(1, remainingBidders)))
    return isLastBidder ? Math.max(0, remaining - 1) : avg
  })
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState('')

  // When the active seat changes (round advances, edit opens/closes), recompute pre-fill.
  useEffect(() => {
    if (activeSeat === null) return
    if (editingSeat !== null) {
      setBidVal(bidsBySeat[editingSeat] ?? 0)
      return
    }
    const remaining = round.cards_per_player - sumSoFar
    const remainingBidders = numPlayers - bidsSubmitted
    const avg = Math.max(0, Math.floor(remaining / Math.max(1, remainingBidders)))
    setBidVal(isLastBidder ? Math.max(0, remaining - 1) : avg)
  }, [activeSeat, editingSeat])

  async function handleConfirm() {
    if (!activePlayer) return
    setErr('')
    setSubmitting(true)
    try {
      await api.rounds.gmBid(game.code, round.round_number, activePlayer.username, bidVal)
      setEditingSeat(null)
      await refresh()
    } catch (e) {
      setErr(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  function handleRowClick(seat) {
    if (seat === editingSeat) {
      // Tap the editing row again to cancel.
      setEditingSeat(null)
      setErr('')
      return
    }
    if (seat === lastConfirmedSeat && !isEditing) {
      setEditingSeat(seat)
      setErr('')
    }
  }

  // Forbidden-bid check only concerns the last bidder's *new* bid.
  // During edit we reopen an earlier slot, so forbidden doesn't apply to bidVal.
  const isForbiddenNewBid =
    !isEditing && isLastBidder && bidVal === forbiddenBidForNext && forbiddenBidForNext >= 0

  return (
    <>
      <div className="rbar">
        <div>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 17, fontWeight: 500 }}>
            Round {round.round_number} — {round.cards_per_player} cards
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Dealer: {playerBySeat[round.dealer_seat]?.username} · ♠ beats all suits
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 20, fontWeight: 500, color: 'var(--accent)' }}>
            {sumSoFar}/{round.cards_per_player}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>tricks claimed</div>
        </div>
      </div>

      <div className="slbl">Enter bids in seat order</div>
      <div className="csect">
        {order.map((seat, i) => {
          const player = playerBySeat[seat]
          if (!player) return null
          const bid = bidsBySeat[seat]
          const confirmed = bid !== undefined
          const isActive = seat === activeSeat
          const isWaitingLast = !confirmed && !isActive
            && bidsSubmitted === numPlayers - 1
            && i === order.findIndex(s => bidsBySeat[s] === undefined)
          const clickable =
            (seat === lastConfirmedSeat && !isEditing)
            || seat === editingSeat

          const subtitle = isActive
            ? (isEditing ? '● Editing' : '● Entering now')
            : confirmed
              ? (seat === lastConfirmedSeat ? 'Tap to edit' : null)
              : (isWaitingLast ? 'Last to bid' : 'Waiting')

          const badge = isWaitingLast && forbiddenBidForNext >= 0
            ? <span className="fpill">≠ {forbiddenBidForNext}</span>
            : null

          return (
            <StepperRow
              key={seat}
              seatNumber={seat + 1}
              name={player.username}
              isDealer={seat === round.dealer_seat}
              subtitle={subtitle}
              badge={badge}
              isActive={isActive}
              stepperValue={bidVal}
              onDecrement={() => setBidVal(v => Math.max(0, v - 1))}
              onIncrement={() => setBidVal(v => Math.min(round.cards_per_player, v + 1))}
              decrementDisabled={bidVal <= 0}
              incrementDisabled={bidVal >= round.cards_per_player}
              confirmedValue={confirmed && !isActive ? bid : undefined}
              clickable={clickable}
              onClick={() => handleRowClick(seat)}
            />
          )
        })}
      </div>

      {!isEditing && isLastBidder && forbiddenBidForNext >= 0 && (
        <div className="alt altw">
          Last bidder cannot bid {forbiddenBidForNext} (would make total equal cards dealt).
        </div>
      )}
      {isForbiddenNewBid && (
        <div
          className="alt altw"
          style={{ background: 'var(--red-bg)', color: 'var(--red-text)', borderColor: 'var(--red-text)' }}
        >
          This bid is forbidden — choose a different value.
        </div>
      )}
      {err && <p className="alt altw">{err}</p>}

      {activePlayer && (
        <button
          className="btnam"
          onClick={handleConfirm}
          disabled={submitting || isForbiddenNewBid}
        >
          {submitting
            ? (isEditing ? 'Updating…' : 'Confirming…')
            : isEditing
              ? `Update ${activePlayer.username}'s bid: ${bidVal}`
              : `Confirm ${activePlayer.username}'s bid: ${bidVal} →`}
        </button>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Bidding — player (read-only) view
// ---------------------------------------------------------------------------

function BiddingPlayerView({ game, round, user, numPlayers }) {
  const order = biddingOrder(round.first_player_seat, numPlayers)
  const bidsBySeat = Object.fromEntries(round.bids.map(b => [b.seat_index, b.bid]))
  const playerBySeat = Object.fromEntries(game.players.map(p => [p.seat_index, p]))
  const myPlayer = game.players.find(p => p.username === user?.username)
  const myBid = myPlayer ? bidsBySeat[myPlayer.seat_index] : undefined
  const nextSeat = order.find(s => bidsBySeat[s] === undefined) ?? null

  return (
    <>
      <div className="rbar">
        <div>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 17, fontWeight: 500 }}>
            Round {round.round_number} — {round.cards_per_player} cards
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 20, fontWeight: 500, color: 'var(--accent)' }}>
            {round.bids.reduce((sum, b) => sum + b.bid, 0)}/{round.cards_per_player}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>tricks claimed</div>
        </div>
      </div>

      {myBid !== undefined && (
        <div className="card" style={{ textAlign: 'center', padding: '20px 14px', marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Your bid this round</div>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 40, fontWeight: 500, color: 'var(--accent)' }}>{myBid}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>tricks</div>
        </div>
      )}

      <div className="slbl">All bids so far</div>
      <div className="csect">
        {order.map(seat => {
          const player = playerBySeat[seat]
          if (!player) return null
          const bid = bidsBySeat[seat]
          const isActive = seat === nextSeat
          return (
            <div key={seat} className={`brow ${isActive ? 'active' : ''}`}>
              <div className="seat" style={isActive ? { background: 'var(--amber)', color: '#fff' } : {}}>{seat + 1}</div>
              <div style={{ flex: 1, fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                {player.username}
                {seat === round.dealer_seat && <span style={{ fontSize: 10, color: 'var(--amber-text)' }}>🂠</span>}
              </div>
              {bid !== undefined
                ? <div className="bconf">{bid}</div>
                : <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {isActive ? 'Thinking…' : 'Waiting'}
                  </span>
              }
            </div>
          )
        })}
      </div>
      <div className="alt alti">Bids are visible to all players in real time.</div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Trick entry — GM view
// ---------------------------------------------------------------------------

function TrickEntryView({ game, round, refresh }) {
  const numPlayers = game.players.length
  const bidsBySeat = Object.fromEntries(round.bids.map(b => [b.seat_index, b.bid]))
  const playerBySeat = Object.fromEntries(game.players.map(p => [p.seat_index, p]))

  // Use bidding order (same as BiddingGMView) so the display matches
  const seats = biddingOrder(round.first_player_seat, numPlayers)

  // Pre-fill everyone with their bid value
  const [tricks, setTricks] = useState(() =>
    Object.fromEntries(seats.map(s => [s, bidsBySeat[s] ?? 0]))
  )
  const [activeSeat, setActiveSeat] = useState(null)
  const [touched, setTouched] = useState(() => new Set())
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState('')

  // The last player in bidding order is auto-resolved to make the total correct
  const lastSeat = seats[seats.length - 1]
  const otherSeats = seats.slice(0, -1)
  const sumOfOthers = otherSeats.reduce((sum, s) => sum + (tricks[s] ?? 0), 0)
  const autoLast = Math.max(0, round.cards_per_player - sumOfOthers)

  // Effective tricks map: others use their state, last is auto-computed
  const effectiveTricks = { ...tricks, [lastSeat]: autoLast }
  const totalTricks = Object.values(effectiveTricks).reduce((a, b) => a + b, 0)
  const valid = totalTricks === round.cards_per_player
  const activeValue = activeSeat !== null ? (effectiveTricks[activeSeat] ?? 0) : 0

  // Every seat must be explicitly acknowledged before confirm enables —
  // otherwise the pre-filled numbers could be committed with one reflex tap.
  const allAcknowledged = seats.every(s => touched.has(s))
  const acknowledgedCount = seats.filter(s => touched.has(s)).length

  function adjustActive(delta) {
    if (activeSeat === null || activeSeat === lastSeat) return
    setTricks(tv => ({
      ...tv,
      [activeSeat]: Math.max(0, (tv[activeSeat] ?? 0) + delta),
    }))
    setTouched(s => new Set(s).add(activeSeat))
  }

  function handleRowClick(seat) {
    // The auto-resolved last seat has no stepper — tapping it only marks
    // it as reviewed so the GM must at least see the computed value.
    if (seat === lastSeat) {
      setTouched(s => new Set(s).add(seat))
      return
    }
    setActiveSeat(s => (s === seat ? null : seat))
    setTouched(s => new Set(s).add(seat))
  }

  async function handleConfirm() {
    if (!valid || !allAcknowledged) return
    setErr('')
    setSubmitting(true)
    try {
      const results = game.players.map(p => ({
        username: p.username,
        tricks_won: effectiveTricks[p.seat_index] ?? 0,
      }))
      await api.rounds.submitResults(game.code, round.round_number, results)
      await refresh()
    } catch (e) {
      setErr(e.message)
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="rbar">
        <div>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 17, fontWeight: 500 }}>
            Round {round.round_number} — {round.cards_per_player} cards
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>Enter tricks won per player</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            fontFamily: 'Lora, serif',
            fontSize: 20,
            fontWeight: 500,
            color: valid ? 'var(--accent)' : 'var(--amber)',
          }}>
            {totalTricks}/{round.cards_per_player}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>tricks</div>
        </div>
      </div>

      <div className="csect">
        {seats.map((seat) => {
          const p = playerBySeat[seat]
          if (!p) return null
          const bid = bidsBySeat[seat] ?? 0
          const t = effectiveTricks[seat] ?? 0
          const isAuto = seat === lastSeat
          const isActive = activeSeat === seat
          const reviewed = touched.has(seat)
          const subtitle = isActive
            ? '● Entering tricks'
            : reviewed
              ? `Bid: ${bid} · Tricks: ${t}${isAuto ? ' (auto)' : ''}`
              : `Bid: ${bid} · Tricks: ${t}${isAuto ? ' (auto)' : ''} · tap to review`

          return (
            <StepperRow
              key={seat}
              seatNumber={seat + 1}
              name={p.username}
              isDealer={seat === round.dealer_seat}
              subtitle={subtitle}
              isActive={isActive}
              stepperValue={activeValue}
              onDecrement={() => adjustActive(-1)}
              onIncrement={() => adjustActive(+1)}
              decrementDisabled={activeValue <= 0}
              incrementDisabled={false}
              confirmedIcon={!isActive && reviewed ? '✓' : null}
              clickable={true}
              onClick={() => handleRowClick(seat)}
            />
          )
        })}
      </div>

      {!allAcknowledged ? (
        <div className="alt altw">
          Review each player before confirming ({acknowledgedCount}/{seats.length} checked).
        </div>
      ) : valid ? (
        <div className="alt alto">✓ All players reviewed — tricks add up to {round.cards_per_player}.</div>
      ) : (
        <div className="alt altw">Total tricks must equal {round.cards_per_player} before confirming.</div>
      )}
      {err && <p className="alt altw">{err}</p>}

      <button className="btnp" onClick={handleConfirm} disabled={!valid || !allAcknowledged || submitting}>
        {submitting ? 'Saving…' : 'Confirm & go to next round →'}
      </button>
    </>
  )
}

// ---------------------------------------------------------------------------
// Playing phase — player view (mini scoreboard with bids)
// ---------------------------------------------------------------------------

function PlayingPlayerView({ round, game, scoreboard }) {
  const bidsByUsername = Object.fromEntries(round.bids.map(b => [b.username, b.bid]))
  const scoreByUsername = Object.fromEntries(
    (scoreboard?.scores ?? []).map(s => [s.username, s.total_score])
  )

  const rows = game.players
    .map(p => ({
      username: p.username,
      bid: bidsByUsername[p.username] ?? '—',
      score: scoreByUsername[p.username] ?? 0,
    }))
    .sort((a, b) => b.score - a.score)

  return (
    <>
      <div className="rbar">
        <div>
          <div style={{ fontFamily: 'Lora, serif', fontSize: 17, fontWeight: 500 }}>
            Round {round.round_number} — {round.cards_per_player} cards
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Waiting for game master to enter tricks…
          </div>
        </div>
      </div>

      <div className="csect">
        {rows.map((row, i) => (
          <div key={row.username} className="strow">
            <div className={`rnk ${i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : ''}`}>
              {i + 1}
            </div>
            <div className="av">{row.username[0].toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{row.username}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                Bid this round: {row.bid}
              </div>
            </div>
            <div style={{
              fontFamily: 'Lora, serif',
              fontSize: 18,
              fontWeight: 500,
              color: row.score < 0 ? 'var(--red-text)' : i === 0 ? 'var(--amber)' : 'var(--text-primary)',
            }}>
              {row.score} pts
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Scores tab
// ---------------------------------------------------------------------------

function ScoresTab({ scoreboard, game, activeRound }) {
  if (!scoreboard) return <Spinner />

  const sorted = [...scoreboard.scores].sort((a, b) => b.total_score - a.total_score)

  return (
    <>
      <div className="slbl">Standings</div>
      <div className="csect">
        {sorted.map((s, i) => (
          <div key={s.username} className="strow">
            <div className={`rnk ${i === 0 ? 'r1' : i === 1 ? 'r2' : i === 2 ? 'r3' : ''}`}>{i + 1}</div>
            <div className="av">{s.username[0].toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{s.username}</div>
              <div className="txt-s">{s.rounds_played} rounds played</div>
            </div>
            <div style={{
              fontFamily: 'Lora, serif',
              fontSize: 18,
              fontWeight: 500,
              color: s.total_score < 0 ? 'var(--red-text)' : i === 0 ? 'var(--amber)' : 'var(--text-primary)',
            }}>
              {s.total_score} pts
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Game info tab
// ---------------------------------------------------------------------------

function GameInfoTab({ game, user, isGM, navigate }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function handleAbandon() {
    if (!confirm('Pause this game? You can resume it later.')) return
    setBusy(true)
    try {
      await api.games.abandon(game.code)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleResume() {
    setBusy(true)
    try {
      await api.games.resume(game.code)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Permanently delete this game? This cannot be undone.')) return
    setBusy(true)
    try {
      await api.games.delete(game.code)
      navigate('/')
    } catch (e) {
      setErr(e.message)
      setBusy(false)
    }
  }

  return (
    <>
      <div className="cblk">
        <div className="clbl">Game code</div>
        <div className="cval">{game.code}</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
          {game.variant === 'pirat_bridge' ? 'Pirat Bridge' : 'Møgspar'}
        </div>
        <div className="row" style={{ marginTop: 14 }}>
          <button className="btns" onClick={() => navigator.clipboard?.writeText(game.code)}>Copy code</button>
        </div>
      </div>

      <div className="slbl">Players</div>
      <div className="csect">
        {game.players.map(p => (
          <div key={p.seat_index} className="prow">
            <div className="seat">{p.seat_index + 1}</div>
            <div style={{ flex: 1, fontSize: 14 }}>{p.username}</div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {p.username === user?.username && <span className="txt-s">you</span>}
              {p.username === game.game_master_username && <span className="bdg bo">GM</span>}
            </div>
          </div>
        ))}
      </div>

      {isGM && (
        <>
          {err && <p className="alt altw">{err}</p>}
          <div className="slbl">Danger zone</div>
          {game.status === 'active' && (
            <button
              className="btns"
              style={{ width: '100%', marginBottom: 8, color: 'var(--amber-text)', borderColor: 'var(--amber)' }}
              onClick={handleAbandon}
              disabled={busy}
            >
              Pause game
            </button>
          )}
          {game.status === 'abandoned' && (
            <button
              className="btns"
              style={{ width: '100%', marginBottom: 8, color: 'var(--accent-text)', borderColor: 'var(--accent)' }}
              onClick={handleResume}
              disabled={busy}
            >
              ▶ Resume game
            </button>
          )}
          <button
            className="btns"
            style={{ width: '100%', color: 'var(--red-text)', borderColor: 'var(--red-text)' }}
            onClick={handleDelete}
            disabled={busy}
          >
            Delete game
          </button>
        </>
      )}
    </>
  )
}
