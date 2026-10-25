import type { Club, ClubSeason, LeagueFixture } from '../match/types'
import { Crest } from './Scorebug'
import { useT } from '../i18n'

const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'}`

/** The viewer's club this season: where it stands, its form, captain and top scorers and assisters. */
export function ClubPanel({ club, season, today }: { club: Club; season: ClubSeason; today?: LeagueFixture }) {
  const t = useT()
  const home = today?.home === club.name
  return (
    <section className="card club-panel" aria-label={t('Your club this season')}>
      <h2>{t('Your club')}</h2>
      <div className="club-head">
        <Crest name={club.name} side="home" code={club.code} color={club.color} />
        <div>
          <div className="club-name">{club.name}</div>
          <div className="club-sub">
            {t('{n} in the league', { n: t.lang === 'es' ? season.position : ordinal(season.position) })} ·{' '}
            {t('{points} pts from {played}', { points: season.points, played: season.played })} ·{' '}
            {t('{w}W {d}D {l}L', { w: season.won, d: season.drawn, l: season.lost })}
          </div>
        </div>
      </div>
      <div className="club-form" aria-label={t('Form, last five')}>
        {season.form.split('').map((r, i) => <span key={i} className={`form-${r}`}>{t.form(r)}</span>)}
      </div>
      <dl className="club-facts">
        {today && (
          <><dt>{t('Today')}</dt>
            <dd>{t(home ? 'v' : 'at')} {home ? today.away : today.home}{today.result ? ` · ${today.result}` : ''}</dd></>
        )}
        <dt>{t('Captain')}</dt><dd>{season.captain}</dd>
      </dl>
      <div className="club-lists">
        <div>
          <h3>{t('Top scorers')}</h3>
          <ol>{season.top_scorers.map((s) => <li key={s.player}><span>{s.player}</span><b>{s.goals}</b></li>)}</ol>
          {season.top_scorers.length === 0 && <p className="empty">{t('No goals yet')}</p>}
        </div>
        <div>
          <h3>{t('Top assists')}</h3>
          <ol>{season.top_assisters.map((s) => <li key={s.player}><span>{s.player}</span><b>{s.assists}</b></li>)}</ol>
          {season.top_assisters.length === 0 && <p className="empty">{t('No assists yet')}</p>}
        </div>
      </div>
    </section>
  )
}
