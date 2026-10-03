import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EVAL_PALETTE } from '../../lib/evalTheme'
import { RadarCategoryChart } from './RadarCategoryChart'

describe('RadarCategoryChart', () => {
  it('shows an empty state with no series data', () => {
    render(<RadarCategoryChart series={[]} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('No category data yet')).toBeInTheDocument()
  })

  it('renders one radar series per provider without crashing', () => {
    const { container } = render(
      <RadarCategoryChart
        series={[
          { label: 'ollama', color: EVAL_PALETTE.dark.primary, byCategory: { structured: { total: 4, passed: 3 } } },
          { label: 'groq', color: EVAL_PALETTE.dark.secondary, byCategory: { structured: { total: 4, passed: 4 } } },
        ]}
        palette={EVAL_PALETTE.dark}
      />,
    )
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument()
  })
})
