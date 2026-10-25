import { useState, useMemo } from 'react'
import type { CommentaryLine, ViewerQuestion } from '../match/types'
import { ClockIcon } from './Icons'

interface AnalystQATableProps {
  questions: ViewerQuestion[]
  lines: CommentaryLine[]
  speakingId: string | null
  onAsk?: (questionText: string) => void
  canAsk?: boolean
}

const DEFAULT_SUGGESTIONS = [
  'Why was that a foul?',
  'Who has been better so far?',
  'What is offside?',
  'What was the key tactical change?',
]

export function AnalystQATable({
  questions,
  lines,
  speakingId,
  onAsk,
  canAsk = true,
}: AnalystQATableProps) {
  const [search, setSearch] = useState('')

  // Map reply_to -> CommentaryLine (Roy's answer)
  const answersByQuestionId = useMemo(() => {
    const map = new Map<string, CommentaryLine>()
    for (const line of lines) {
      if (line.reply_to) {
        map.set(line.reply_to, line)
      }
    }
    return map
  }, [lines])

  // Combine questions with their answers, newest first
  const qaItems = useMemo(() => {
    return [...questions].reverse().map((q) => {
      const answer = answersByQuestionId.get(q.id)
      return {
        question: q,
        answer,
        isAnswered: Boolean(answer),
      }
    })
  }, [questions, answersByQuestionId])

  const filteredItems = useMemo(() => {
    if (!search.trim()) return qaItems
    const query = search.toLowerCase()
    return qaItems.filter((item) => {
      const matchQ = item.question.text.toLowerCase().includes(query)
      const matchA = item.answer?.text.toLowerCase().includes(query) ?? false
      return matchQ || matchA
    })
  }, [qaItems, search])

  return (
    <section className="card qa-table-card" aria-label="Questions Table">
      <div className="qa-header">
        <div className="qa-title-group">
          <div className="qa-badge-icon" aria-hidden="true">💬</div>
          <div>
            <h2>Questions</h2>
            <p className="qa-subtitle">
              Your questions and Roy's real-time personalized analysis
            </p>
          </div>
        </div>

        <div className="qa-stats-chips">
          <span className="qa-stat-pill total">
            <strong>{qaItems.length}</strong> {qaItems.length === 1 ? 'Question' : 'Questions'}
          </span>
        </div>
      </div>

      {qaItems.length > 0 && (
        <div className="qa-toolbar">
          <div className="qa-search-box">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search questions..."
              aria-label="Search questions"
            />
            {search && (
              <button
                type="button"
                className="qa-search-clear"
                onClick={() => setSearch('')}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      )}

      {qaItems.length === 0 ? (
        <div className="qa-empty-state">
          <div className="qa-empty-icon" aria-hidden="true">🎙️</div>
          <h3>No questions asked yet</h3>
          <p>
            Ask Roy about fouls, tactics, key moments, or rules using the question box or microphone.
            His answers will appear here in real time!
          </p>
          {onAsk && canAsk && (
            <div className="qa-empty-suggestions">
              <span className="qa-suggestions-label">Try asking:</span>
              <div className="qa-suggestions-list">
                {DEFAULT_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="chip qa-suggestion-chip"
                    onClick={() => onAsk(s)}
                  >
                    + {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="qa-empty-filter">
          <p>No questions match "{search}".</p>
          <button type="button" className="chip" onClick={() => setSearch('')}>
            Clear search
          </button>
        </div>
      ) : (
        <div className="qa-table-wrapper">
          <table className="qa-table">
            <thead>
              <tr>
                <th className="col-clock">Time</th>
                <th className="col-question">Question (You)</th>
                <th className="col-answer">Roy's Analysis</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map(({ question, answer, isAnswered }) => {
                const isSpeaking = answer ? answer.id === speakingId : false

                return (
                  <tr
                    key={question.id}
                    className={`qa-row ${isSpeaking ? 'speaking' : ''}`}
                  >
                    {/* Time / Clock Column */}
                    <td className="col-clock">
                      <span className="qa-clock-badge" title={`Asked at ${question.clock}`}>
                        <ClockIcon size={13} />
                        <span>{question.clock}</span>
                      </span>
                    </td>

                    {/* Question Column */}
                    <td className="col-question">
                      <div className="qa-question-content">
                        <span className="qa-avatar you" aria-hidden="true">You</span>
                        <div className="qa-question-text">
                          <p>{question.text}</p>
                        </div>
                      </div>
                    </td>

                    {/* Answer Column */}
                    <td className="col-answer">
                      {isAnswered && answer ? (
                        <div className="qa-answer-content">
                          <span className="qa-avatar roy" aria-hidden="true">R</span>
                          <div className="qa-answer-body">
                            <div className="qa-answer-meta">
                              <span className="qa-speaker-name">Roy (Analyst)</span>
                              {answer.level && <span className="level-tag">{answer.level}</span>}
                              {isSpeaking && (
                                <span className="on-air qa-on-air-badge">
                                  <span className="wave"><i /><i /><i /><i /></span> On Air
                                </span>
                              )}
                            </div>
                            <p className="qa-answer-text">{answer.text}</p>
                          </div>
                        </div>
                      ) : (
                        <div className="qa-thinking-indicator">
                          <span className="qa-spinner" aria-hidden="true" />
                          <span className="qa-thinking-text">Roy is analyzing match data...</span>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
