const BASE = '/api'

function getToken() {
  return localStorage.getItem('token')
}

async function request(method, path, body = undefined, auth = true) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw Object.assign(new Error(err.detail ?? 'Request failed'), { status: res.status })
  }

  const text = await res.text()
  return text ? JSON.parse(text) : null
}

// Auth
export const api = {
  auth: {
    config: () => request('GET', '/auth/config', undefined, false),
    register: (username, email, password, invite_code = '') =>
      request('POST', '/auth/register', { username, email, password, invite_code }, false),

    login: async (username, password) => {
      const form = new URLSearchParams({ username, password })
      const res = await fetch(`${BASE}/auth/login`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Login failed' }))
        throw Object.assign(new Error(err.detail ?? 'Login failed'), { status: res.status })
      }
      return res.json()
    },

    me: () => request('GET', '/auth/me'),
  },

  games: {
    list: () => request('GET', '/games'),
    create: () => request('POST', '/games'),
    get: (code) => request('GET', `/games/${code}`),
    join: (code) => request('POST', `/games/${code}/join`),
    start: (code) => request('POST', `/games/${code}/start`),
    reorder: (code, order) => request('POST', `/games/${code}/reorder`, { order }),
    setDealer: (code, dealer_username) => request('POST', `/games/${code}/dealer`, { dealer_username }),
    setMaxCards: (code, max_cards) => request('POST', `/games/${code}/max-cards`, { max_cards }),
    setVariant: (code, variant) => request('POST', `/games/${code}/variant`, { variant }),
    addPlayer: (code, username) => request('POST', `/games/${code}/gm-add`, { username }),
    removePlayer: (code, player_id) => request('DELETE', `/games/${code}/players/${player_id}`),
    finish: (code) => request('POST', `/games/${code}/finish`),
    abandon: (code) => request('POST', `/games/${code}/abandon`),
    resume: (code) => request('POST', `/games/${code}/resume`),
    delete: (code) => request('DELETE', `/games/${code}`),
    scoreboard: (code) => request('GET', `/games/${code}/score`),
  },

  players: {
    search: (q = '') => request('GET', `/players?q=${encodeURIComponent(q)}`),
  },

  stats: {
    leaderboard: (variant) => request('GET', `/stats/leaderboard${variant ? `?variant=${variant}` : ''}`),
    me: (variant) => request('GET', `/stats/me${variant ? `?variant=${variant}` : ''}`),
    scoped: ({ scope, match, players, game_code, variant } = {}) => {
      const params = new URLSearchParams()
      params.set('scope', scope)
      if (match) params.set('match', match)
      if (players && players.length) params.set('players', players.join(','))
      if (game_code) params.set('game_code', game_code)
      if (variant) params.set('variant', variant)
      return request('GET', `/stats/scoped?${params.toString()}`)
    },
    lineups: ({ min_games = 2, variant } = {}) => {
      const params = new URLSearchParams()
      params.set('min_games', String(min_games))
      if (variant) params.set('variant', variant)
      return request('GET', `/stats/lineups?${params.toString()}`)
    },
  },

  rounds: {
    create: (code, cards_per_player) =>
      request('POST', `/games/${code}/rounds`, { cards_per_player }),
    get: (code, roundNumber) =>
      request('GET', `/games/${code}/rounds/${roundNumber}`),
    bid: (code, roundNumber, bid) =>
      request('POST', `/games/${code}/rounds/${roundNumber}/bid`, { bid }),
    gmBid: (code, roundNumber, username, bid) =>
      request('POST', `/games/${code}/rounds/${roundNumber}/gm-bid`, { username, bid }),
    submitResults: (code, roundNumber, results) =>
      request('POST', `/games/${code}/rounds/${roundNumber}/results`, { results }),
    getResults: (code, roundNumber) =>
      request('GET', `/games/${code}/rounds/${roundNumber}/results`),
  },
}
