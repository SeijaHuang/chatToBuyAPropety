import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { SkeletonText, SkeletonMessage } from '@/components/shared/Skeleton'

describe('SkeletonText', () => {
  it('has animate-pulse class', () => {
    const { container } = render(<SkeletonText />)
    expect((container.firstChild as HTMLElement).className).toContain('animate-pulse')
  })
})

describe('SkeletonMessage', () => {
  it('has animate-pulse class on inner elements', () => {
    const { container } = render(<SkeletonMessage />)
    const pulseElements = container.querySelectorAll('.animate-pulse')
    expect(pulseElements.length).toBeGreaterThan(0)
  })
})
