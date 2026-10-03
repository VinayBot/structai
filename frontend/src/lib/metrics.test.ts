import { describe, expect, it } from 'vitest'
import { parsePrometheusText } from './metrics'

describe('parsePrometheusText', () => {
  it('ignores comment and type lines', () => {
    const families = parsePrometheusText(
      '# HELP structai_rate_limit_hits_total Requests rejected\n' +
        '# TYPE structai_rate_limit_hits_total counter\n' +
        'structai_rate_limit_hits_total 0.0\n',
    )
    expect(families).toHaveLength(1)
    expect(families[0].name).toBe('structai_rate_limit_hits_total')
    expect(families[0].samples[0].value).toBe(0)
    expect(families[0].samples[0].labels).toEqual({})
  })

  it('parses labeled samples with multiple label pairs', () => {
    const families = parsePrometheusText(
      'structai_http_requests_total{method="GET",path="/health",status_code="200"} 3.0\n',
    )
    expect(families[0].samples[0].labels).toEqual({
      method: 'GET',
      path: '/health',
      status_code: '200',
    })
    expect(families[0].samples[0].value).toBe(3)
  })

  it('groups multiple samples of the same metric name together', () => {
    const families = parsePrometheusText(
      'python_gc_objects_collected_total{generation="0"} 318.0\n' +
        'python_gc_objects_collected_total{generation="1"} 0.0\n',
    )
    expect(families).toHaveLength(1)
    expect(families[0].samples).toHaveLength(2)
  })

  it('parses scientific-notation and bucket-style values', () => {
    const families = parsePrometheusText(
      'structai_http_requests_created{method="GET"} 1.790889157047507e+09\n' +
        'structai_structured_answer_attempts_bucket{le="1.0"} 0.0\n',
    )
    expect(families).toHaveLength(2)
    expect(families[0].samples[0].value).toBeCloseTo(1.790889157047507e9)
  })

  it('skips blank lines and returns no families for empty input', () => {
    expect(parsePrometheusText('\n\n   \n')).toEqual([])
  })
})
