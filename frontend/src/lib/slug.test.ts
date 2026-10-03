import { describe, expect, it } from 'vitest'
import { slugify } from './slug'

describe('slugify', () => {
  it.each([
    ['UserName', 'user_name'],
    ['already_snake', 'already_snake'],
    ['Name', 'name'],
    ['XMLParser', 'xml_parser'],
    ['user name', 'user_name'],
    ['user-name!', 'user_name'],
    ['  spaced out  ', 'spaced_out'],
    ['', ''],
  ])('converts %s to %s', (input, expected) => {
    expect(slugify(input)).toBe(expected)
  })
})
