import { useState, useEffect, useMemo } from 'react'
import type { Club, PlayerProfile, TeamInfo } from '../match/types'
import { Crest } from './Scorebug'

interface PlayerInvestigationProps {
  homeTeam?: TeamInfo
  awayTeam?: TeamInfo
  clubs?: Club[]
  onAskRoy?: (question: string) => void
}

export function PlayerInvestigation({
  homeTeam,
  awayTeam,
  clubs,
  onAskRoy,
}: PlayerInvestigationProps) {
  // Available players from the current match teams
  const availablePlayers = useMemo(() => {
    const list: { name: string; number?: number; position?: string; teamName: string }[] = []

    if (homeTeam?.players) {
      for (const p of homeTeam.players) {
        list.push({ ...p, teamName: homeTeam.name })
      }
    }
    if (awayTeam?.players) {
      for (const p of awayTeam.players) {
        list.push({ ...p, teamName: awayTeam.name })
      }
    }

    return list
  }, [homeTeam, awayTeam])

  // Default to first starter or key forward
  const defaultPlayerName = useMemo(() => {
    const firstStarter = availablePlayers.find((p) => p.position?.includes('Forward') || p.position?.includes('Midfield'))
    return firstStarter ? firstStarter.name : availablePlayers[0]?.name ?? 'M. Ferro'
  }, [availablePlayers])

  const [selectedPlayer, setSelectedPlayer] = useState<string>(defaultPlayerName)
  const [profile, setProfile] = useState<PlayerProfile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [customSearch, setCustomSearch] = useState('')

  useEffect(() => {
    if (!selectedPlayer) return

    let cancelled = false

    fetch(`/api/league/player?name=${encodeURIComponent(selectedPlayer)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Player not found (${res.status})`)
        return res.json()
      })
      .then((data: PlayerProfile) => {
        if (!cancelled) {
          setProfile(data)
          setError(null)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load player data')
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [selectedPlayer])

  const selectPlayer = (name: string) => {
    setLoading(true)
    setError(null)
    setSelectedPlayer(name)
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (customSearch.trim()) {
      selectPlayer(customSearch.trim())
      setCustomSearch('')
    }
  }

  // Quick prompt triggers to ask Roy
  const askAboutForm = () => {
    if (!profile) return
    onAskRoy?.(`How has ${profile.name} performed in his last 5 games?`)
  }

  const askAboutTactics = () => {
    if (!profile) return
    onAskRoy?.(`What is ${profile.name}'s key tactical role today?`)
  }

  const askAboutClinical = () => {
    if (!profile) return
    onAskRoy?.(`Is ${profile.name} clinical in front of goal based on his form?`)
  }

  const clubInfo = clubs?.find((c) => c.name === profile?.team)

  return (
    <section className="card player-investigation" aria-label="Investigate player: last games data">
      <div className="pi-header">
        <div className="pi-title-row">
          <span className="pi-badge" aria-hidden="true">🔬 ANALYST SCOUT</span>
          <h2>Investigate Player</h2>
        </div>
        <p className="pi-subtitle">
          Detailed match performance, rating, and form across the last games
        </p>
      </div>

      {/* Quick Player Picker Chips */}
      <div className="pi-selector-section">
        <div className="pi-player-chips" role="group" aria-label="Select player to investigate">
          {availablePlayers.slice(0, 10).map((p) => {
            const isSelected = selectedPlayer.toLowerCase() === p.name.toLowerCase()
            return (
              <button
                key={p.name}
                type="button"
                className={`pi-chip ${isSelected ? 'active' : ''}`}
                onClick={() => selectPlayer(p.name)}
                title={`${p.name} (${p.position ?? 'Player'} · ${p.teamName})`}
              >
                <span className="pi-chip-num">{p.number ?? '•'}</span>
                <span className="pi-chip-name">{p.name}</span>
                <span className="pi-chip-team">{p.teamName.split(' ')[0]}</span>
              </button>
            )
          })}
        </div>

        {/* Custom Search Form */}
        <form className="pi-search-form" onSubmit={handleSearchSubmit}>
          <input
            type="text"
            value={customSearch}
            onChange={(e) => setCustomSearch(e.target.value)}
            placeholder="Search any player in league..."
            aria-label="Search any player in league"
          />
          <button type="submit" disabled={!customSearch.trim()}>
            Inspect
          </button>
        </form>
      </div>

      {loading && (
        <div className="pi-loading">
          <span className="qa-spinner" aria-hidden="true" />
          <span>Analyzing player match reports and tactical data...</span>
        </div>
      )}

      {error && (
        <div className="pi-error">
          <p>{error}</p>
        </div>
      )}

      {profile && !loading && (
        <div className="pi-body">
          {/* Player Bio & Season Stats Bar */}
          <div className="pi-profile-card">
            <div className="pi-profile-left">
              <div className="pi-avatar-circle">
                <span className="pi-jersey-num">#{profile.number}</span>
              </div>
              <div className="pi-info">
                <div className="pi-name-row">
                  <h3 className="pi-player-name">{profile.name}</h3>
                  {profile.is_captain && <span className="pi-cap-badge">CAPTAIN</span>}
                </div>
                <div className="pi-sub-row">
                  {clubInfo && (
                    <Crest name={profile.team} side="home" code={clubInfo.code} color={clubInfo.color} />
                  )}
                  <span className="pi-team-name">{profile.team}</span>
                  <span className="pi-dot">·</span>
                  <span className="pi-pos">{profile.position}</span>
                </div>
              </div>
            </div>

            {/* Season KPI Summary */}
            <div className="pi-kpis">
              <div className="pi-kpi">
                <span className="pi-kpi-val">{profile.season.goals}</span>
                <span className="pi-kpi-label">Goals</span>
              </div>
              <div className="pi-kpi">
                <span className="pi-kpi-val">{profile.season.assists}</span>
                <span className="pi-kpi-label">Assists</span>
              </div>
              <div className="pi-kpi">
                <span className="pi-kpi-val">{profile.season.played}</span>
                <span className="pi-kpi-label">Games</span>
              </div>
              <div className="pi-kpi">
                <span className="pi-kpi-val pi-rating">{profile.season.avg_rating}</span>
                <span className="pi-kpi-label">Avg Rating</span>
              </div>
            </div>
          </div>

          {/* Last Games Data Table */}
          <div className="pi-last-games">
            <div className="pi-section-head">
              <h4>Last 5 Matches Performance</h4>
              <div className="pi-form-pills">
                {profile.last_games.map((g, idx) => (
                  <span key={idx} className={`pi-form-pill res-${g.result}`}>
                    {g.result}
                  </span>
                ))}
              </div>
            </div>

            <div className="pi-table-wrapper">
              <table className="pi-table">
                <thead>
                  <tr>
                    <th>Match</th>
                    <th>Opponent</th>
                    <th>Result</th>
                    <th>Goals</th>
                    <th>Assists</th>
                    <th>Cards</th>
                    <th>Rating</th>
                  </tr>
                </thead>
                <tbody>
                  {profile.last_games.map((g) => (
                    <tr key={g.match_id}>
                      <td className="pi-col-rnd">R{g.round}</td>
                      <td className="pi-col-opp">
                        <span className="pi-venue-tag">{g.is_home ? 'H' : 'A'}</span>
                        <span className="pi-opp-name">{g.opponent}</span>
                      </td>
                      <td className="pi-col-res">
                        <span className={`pi-res-tag res-${g.result}`}>
                          {g.result} {g.score}
                        </span>
                      </td>
                      <td className="pi-col-goals">
                        {g.goals > 0 ? (
                          <span className="pi-stat-hit">⚽ {g.goals}</span>
                        ) : (
                          <span className="pi-stat-zero">-</span>
                        )}
                      </td>
                      <td className="pi-col-assists">
                        {g.assists > 0 ? (
                          <span className="pi-stat-hit">👟 {g.assists}</span>
                        ) : (
                          <span className="pi-stat-zero">-</span>
                        )}
                      </td>
                      <td className="pi-col-cards">
                        {g.cards.length > 0 ? (
                          <span className="pi-card-tag">{g.cards.join(', ')}</span>
                        ) : (
                          <span className="pi-stat-zero">-</span>
                        )}
                      </td>
                      <td className="pi-col-rating">
                        <span className={`pi-match-rating ${g.rating >= 7.5 ? 'high' : g.rating >= 6.5 ? 'med' : 'low'}`}>
                          ★ {g.rating.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Quick Roy Action Prompts */}
          {onAskRoy && (
            <div className="pi-prompts">
              <span className="pi-prompts-label">Ask Roy about {profile.name}:</span>
              <div className="pi-prompts-list">
                <button type="button" className="chip pi-prompt-btn" onClick={askAboutForm}>
                  💬 How has {profile.name} performed in his last 5 games?
                </button>
                <button type="button" className="chip pi-prompt-btn" onClick={askAboutTactics}>
                  💬 What is {profile.name}'s key tactical role today?
                </button>
                <button type="button" className="chip pi-prompt-btn" onClick={askAboutClinical}>
                  💬 Is {profile.name} clinical in front of goal?
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
