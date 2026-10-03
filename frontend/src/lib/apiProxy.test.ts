import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import viteConfig from '../../vite.config'

const dirname = path.dirname(fileURLToPath(import.meta.url))

function extractApiPathPrefixes(source: string): Set<string> {
  const prefixes = new Set<string>()
  const patterns = [/(['"`])(\/[a-zA-Z][a-zA-Z0-9_-]*)/g, /\$\{API_BASE\}(\/[a-zA-Z][a-zA-Z0-9_-]*)/g]
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) {
      prefixes.add(match[match.length - 1])
    }
  }
  return prefixes
}

describe('vite dev-server proxy coverage', () => {
  it('proxies every API path prefix referenced in lib/api.ts', () => {
    const apiSource = readFileSync(path.join(dirname, 'api.ts'), 'utf-8')
    const usedPrefixes = extractApiPathPrefixes(apiSource)
    expect(usedPrefixes.size).toBeGreaterThan(0)

    const proxied = new Set(Object.keys(viteConfig.server?.proxy ?? {}))

    const missing = [...usedPrefixes].filter((prefix) => !proxied.has(prefix))
    expect(missing).toEqual([])
  })
})
