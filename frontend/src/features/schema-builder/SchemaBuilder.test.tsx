import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { SchemaDef } from '../../lib/types'
import { emptyField, SchemaBuilder } from './SchemaBuilder'

function Harness() {
  const [schema, setSchema] = useState<SchemaDef>({ fields: [emptyField()] })
  return <SchemaBuilder schema={schema} onChange={setSchema} />
}

describe('SchemaBuilder', () => {
  it('starts with one field whose remove button is disabled', () => {
    render(<Harness />)
    expect(screen.getAllByPlaceholderText('field_name')).toHaveLength(1)
    expect(screen.getByLabelText('remove field 1')).toBeDisabled()
  })

  it('adds a field and enables removal once there are two', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByText('+ Add field'))

    expect(screen.getAllByPlaceholderText('field_name')).toHaveLength(2)
    expect(screen.getByLabelText('remove field 1')).toBeEnabled()
    expect(screen.getByLabelText('remove field 2')).toBeEnabled()
  })

  it('removes a field down to one and disables removal again', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByText('+ Add field'))
    await user.click(screen.getByLabelText('remove field 2'))

    expect(screen.getAllByPlaceholderText('field_name')).toHaveLength(1)
    expect(screen.getByLabelText('remove field 1')).toBeDisabled()
  })

  it('updates a field name as the user types', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const nameInput = screen.getByPlaceholderText('field_name')
    await user.type(nameInput, 'answer')

    expect(nameInput).toHaveValue('answer')
  })

  it('shows a hint and auto-corrects a non-snake-case name on blur', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const nameInput = screen.getByPlaceholderText('field_name')
    await user.type(nameInput, 'UserName')
    expect(screen.getByText('will be saved as "user_name"')).toBeInTheDocument()

    await user.tab()
    expect(nameInput).toHaveValue('user_name')
    expect(screen.queryByText('will be saved as "user_name"')).not.toBeInTheDocument()
  })

  it('does not show the hint again for the same field once it has been corrected', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const nameInput = screen.getByPlaceholderText('field_name')
    await user.type(nameInput, 'UserName')
    await user.tab()

    await user.clear(nameInput)
    await user.type(nameInput, 'AnotherBadName')

    expect(screen.queryByText(/will be saved as/)).not.toBeInTheDocument()
  })
})
