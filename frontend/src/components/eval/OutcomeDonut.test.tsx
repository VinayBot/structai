import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EVAL_PALETTE } from '../../lib/evalTheme'
import { OutcomeDonut } from './OutcomeDonut'

describe('OutcomeDonut', () => {
  it('shows an empty state when there are no runs', () => {
    render(<OutcomeDonut passed={0} failed={0} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('No runs yet')).toBeInTheDocument()
  })

  it('renders the pass percentage and count without crashing', () => {
    render(<OutcomeDonut passed={3} failed={1} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('3 / 4 passed')).toBeInTheDocument()
  })
})
