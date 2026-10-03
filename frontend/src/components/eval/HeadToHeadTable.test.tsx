import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EVAL_PALETTE } from '../../lib/evalTheme'
import { HeadToHeadTable } from './HeadToHeadTable'

describe('HeadToHeadTable', () => {
  it('shows an empty state with no category data', () => {
    render(<HeadToHeadTable series={[]} />)
    expect(screen.getByText('No data yet')).toBeInTheDocument()
  })

  it('hints to run both providers when only one has data', () => {
    render(
      <HeadToHeadTable
        series={[
          {
            label: 'ollama',
            color: EVAL_PALETTE.dark.primary,
            byCategory: { structured: { total: 4, passed: 3 } },
            avgLatencyByCategory: { structured: 120 },
          },
        ]}
      />,
    )
    expect(screen.getByText('Run both Ollama and Groq to compare head-to-head.')).toBeInTheDocument()
  })

  it('renders a row per category comparing both providers', () => {
    render(
      <HeadToHeadTable
        series={[
          {
            label: 'ollama',
            color: EVAL_PALETTE.dark.primary,
            byCategory: { structured: { total: 4, passed: 3 } },
            avgLatencyByCategory: { structured: 120 },
          },
          {
            label: 'groq',
            color: EVAL_PALETTE.dark.secondary,
            byCategory: { structured: { total: 4, passed: 4 } },
            avgLatencyByCategory: { structured: 90 },
          },
        ]}
      />,
    )
    expect(screen.getByText('structured')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })
})
