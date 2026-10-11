import { afterEach, describe, expect, it, vi } from 'vitest'
import { createTopicId } from './topic-id'

afterEach(() => vi.unstubAllGlobals())

describe('topic draft UUID', () => {
  it('uses native randomUUID when available', () => {
    const id = '68317f4b-7445-45bf-8cbb-0c3ba05c5a50'
    const randomUUID = vi.fn().mockReturnValue(id)
    const getRandomValues = vi.fn()
    vi.stubGlobal('crypto', { randomUUID, getRandomValues })
    expect(createTopicId()).toBe(id)
    expect(randomUUID).toHaveBeenCalledOnce()
    expect(getRandomValues).not.toHaveBeenCalled()
  })

  it.each([
    [0, '00000000-0000-4000-8000-000000000000'],
    [255, 'ffffffff-ffff-4fff-bfff-ffffffffffff'],
  ])('sets UUID v4 version and variant bits with random bytes of %s', (value, expected) => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => bytes.fill(value as number))
    vi.stubGlobal('crypto', { getRandomValues })
    expect(createTopicId()).toBe(expected)
    expect(getRandomValues).toHaveBeenCalledOnce()
    expect(getRandomValues.mock.calls[0][0]).toHaveLength(16)
  })

  it('requests fresh random bytes for each new draft', () => {
    let next = 0
    vi.stubGlobal('crypto', { getRandomValues: (bytes: Uint8Array) => bytes.fill(next++) })
    expect(createTopicId()).not.toBe(createTopicId())
  })

  it.each([undefined, {}])('fails safely when secure randomness is missing', source => {
    vi.stubGlobal('crypto', source)
    expect(() => createTopicId()).toThrow('Secure random generation is unavailable')
  })

  it('does not replace a failed secure generator with weak randomness', () => {
    vi.stubGlobal('crypto', { getRandomValues: () => { throw new Error('random source failed') } })
    expect(() => createTopicId()).toThrow('random source failed')
  })
})
