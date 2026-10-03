import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EVAL_PALETTE } from '../../lib/evalTheme'
import { FirstTryGauge } from './FirstTryGauge'

describe('FirstTryGauge', () => {
  it('shows an empty state when the rate is null', () => {
    render(<FirstTryGauge firstTryRate={null} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('No runs yet')).toBeInTheDocument()
  })

  it('renders the rounded percentage without crashing', () => {
    render(<FirstTryGauge firstTryRate={0.666} palette={EVAL_PALETTE.dark} />)
    expect(screen.getByText('67%')).toBeInTheDocument()
    expect(screen.getByText('first-try pass rate')).toBeInTheDocument()
  })
})
