import type { ReactNode } from 'react'
import type { MatchEvent, Moment, RankedEvent } from '../match/types'
import { useT } from '../i18n'
import { BallIcon, CardIcon, ClockIcon, FlagIcon, SwapIcon, TargetIcon, WhistleIcon } from './Icons'

function icon(e: MatchEvent, m: Moment): ReactNode {
  if (m.kind === 'goal') return <BallIcon />
  const card = e.card ?? e.foul?.card
  if (card) return <CardIcon color={/red|second/i.test(card) ? 'red' : 'yellow'} />
  if (e.type === 'Shot') return <TargetIcon />
  if (e.type === 'Offside' || m.reason.includes('corner')) return <FlagIcon />
  if (e.type === 'Substitution') return <SwapIcon />
  if (e.type === 'Foul Committed') return <WhistleIcon />
  if (e.type === 'Half Start' || e.type === 'Half End') return <ClockIcon />
  return <span className="dot" />
}

/** A real key moment: a goal, a card, a penalty, or a big chance. Not every carry into the box. */
function isKeyMoment({ event, moment }: RankedEvent): boolean {
  if (moment.kind === 'phase') return false
  return moment.kind === 'goal' || Boolean(event.card ?? event.foul?.card) || moment.score >= 7
}

/** The match's key moments, newest first, with the reason each mattered. */
export function EventTicker({ events, homeTeam }: { events: RankedEvent[]; homeTeam: string }) {
  const t = useT()
  const key = events.filter(isKeyMoment).slice(0, 10)
  return (
    <section className="card ticker" aria-label={t('Key moments')}>
      <h2>{t('Key moments')}</h2>
      {key.length === 0 ? (
        <p className="empty">{t('Goals, cards and big chances will appear here.')}</p>
      ) : (
        <ol>
          {key.map(({ event: e, moment }) => (
            <li key={e.id} className={e.team === homeTeam ? 'home' : 'away'}
              data-goal={moment.kind === 'goal'}>
              <span className="minute">{e.minute}'</span>
              <span className="icon" aria-hidden="true">{icon(e, moment)}</span>
              <span className="what">
                <strong>{e.player?.split(' ').slice(-1)[0] ?? e.team}</strong>
                <span className="reason">{t.reason(moment.reason)}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
