import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { JsonView } from './JsonView'

describe('JsonView', () => {
  it('renders primitive values with their JSON representation', () => {
    render(<JsonView data={{ name: 'alice', age: 30, active: true, note: null }} />)

    expect(screen.getByText('"alice"')).toBeInTheDocument()
    expect(screen.getByText('30')).toBeInTheDocument()
    expect(screen.getByText('true')).toBeInTheDocument()
    expect(screen.getByText('null')).toBeInTheDocument()
  })

  it('collapses a nested object by default and expands it on click', async () => {
    render(<JsonView data={{ outer: { inner: 'secret' } }} />)

    expect(screen.queryByText('"secret"')).not.toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByText('outer:', { exact: false }))

    expect(await screen.findByText('"secret"')).toBeInTheDocument()
  })

  it('renders empty objects and arrays inline', () => {
    render(<JsonView data={{ emptyObj: {}, emptyArr: [] }} />)

    expect(screen.getByText('{}')).toBeInTheDocument()
    expect(screen.getByText('[]')).toBeInTheDocument()
  })
})
