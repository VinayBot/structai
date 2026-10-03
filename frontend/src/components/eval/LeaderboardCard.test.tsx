import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LeaderboardCard } from './LeaderboardCard'

describe('LeaderboardCard', () => {
  it('shows an empty state with no entries', () => {
    render(<LeaderboardCard entries={[]} />)
    expect(screen.getByText('No runs yet')).toBeInTheDocument()
  })

  it('renders one row per leaderboard entry', () => {
    render(
      <LeaderboardCard
        entries={[
          { provider: 'ollama', model: 'llama3', runs: 5, avg_pass_rate: 0.9, avg_latency_ms: 120.4 },
          { provider: 'groq', model: null, runs: 3, avg_pass_rate: 0.75, avg_latency_ms: 80.1 },
        ]}
      />,
    )
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByText('ollama')).toBeInTheDocument()
    expect(screen.getByText('90%')).toBeInTheDocument()
  })
})
