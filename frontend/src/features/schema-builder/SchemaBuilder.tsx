import { useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { FIELD_TYPES, type FieldDef, type SchemaDef } from '../../lib/types'
import { slugify } from '../../lib/slug'

export function emptyField(): FieldDef {
  return { name: '', type: 'string', description: '', required: true }
}

interface SchemaBuilderProps {
  schema: SchemaDef
  onChange: (schema: SchemaDef) => void
}

export function SchemaBuilder({ schema, onChange }: SchemaBuilderProps) {
  const [correctedIndices, setCorrectedIndices] = useState<Set<number>>(new Set())

  function updateField(index: number, patch: Partial<FieldDef>) {
    const fields = schema.fields.map((f, i) => (i === index ? { ...f, ...patch } : f))
    onChange({ fields })
  }

  function addField() {
    onChange({ fields: [...schema.fields, emptyField()] })
  }

  function removeField(index: number) {
    onChange({ fields: schema.fields.filter((_, i) => i !== index) })
  }

  function handleNameBlur(index: number) {
    const field = schema.fields[index]
    const suggested = slugify(field.name)
    if (suggested && suggested !== field.name) {
      updateField(index, { name: suggested })
    }
    setCorrectedIndices((prev) => new Set(prev).add(index))
  }

  return (
    <div className="space-y-2">
      {schema.fields.map((field, index) => {
        const suggested = slugify(field.name)
        const showHint = field.name.trim() !== '' && suggested !== field.name && !correctedIndices.has(index)

        return (
          <div key={index} className="flex flex-wrap items-start gap-2 rounded-lg border border-border bg-surface-raised p-2">
            <div className="w-36">
              <Input
                placeholder="field_name"
                value={field.name}
                onChange={(e) => updateField(index, { name: e.target.value })}
                onBlur={() => handleNameBlur(index)}
                className="w-36"
              />
              {showHint && <p className="mt-0.5 text-[11px] text-text-dim">will be saved as "{suggested}"</p>}
            </div>
            <Select
              value={field.type}
              onChange={(e) => updateField(index, { type: e.target.value as FieldDef['type'] })}
              className="w-32"
            >
              {FIELD_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>
            <Input
              placeholder="description (optional)"
              value={field.description}
              onChange={(e) => updateField(index, { description: e.target.value })}
              className="min-w-40 flex-1"
            />
            <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-text-dim">
              <input
                type="checkbox"
                checked={field.required}
                onChange={(e) => updateField(index, { required: e.target.checked })}
              />
              required
            </label>
            <Button
              type="button"
              variant="ghost"
              onClick={() => removeField(index)}
              disabled={schema.fields.length === 1}
              aria-label={`remove field ${index + 1}`}
            >
              ✕
            </Button>
          </div>
        )
      })}
      <Button type="button" variant="secondary" onClick={addField}>
        + Add field
      </Button>
    </div>
  )
}
