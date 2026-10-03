import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EVAL_PALETTE } from '../../lib/evalTheme'
import { GroupedLatencyBars } from './GroupedLatencyBars'

describe('GroupedLatencyBars', () => {
  it('shows an empty state with no series data', () => {
    render(<GroupedLatencyBars series={[]} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('No latency data yet')).toBeInTheDocument()
  })

  it('renders bars for each category without crashing', () => {
    const { container } = render(
      <GroupedLatencyBars
        series={[
          { label: 'ollama', color: EVAL_PALETTE.dark.primary, avgLatencyByCategory: { structured: 120.4, extraction: 80.1 } },
          { label: 'groq', color: EVAL_PALETTE.dark.secondary, avgLatencyByCategory: { structured: 90.2 } },
        ]}
        palette={EVAL_PALETTE.dark}
      />,
    )
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })
})
