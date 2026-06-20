import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ModuleProgress } from '@/components/ModuleProgress'
import { MODULE_ID } from '@/constants'

describe('ModuleProgress', () => {
  it('shows step number for a completed module', () => {
    render(
      <ModuleProgress
        completionStatus={{ M1: true, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M2}
      />,
    )
    expect(screen.getByText('1')).toBeTruthy()
  })

  it('applies animate-pulse class to current module node', () => {
    const { container } = render(
      <ModuleProgress
        completionStatus={{ M1: false, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M1}
      />,
    )
    const pulsingNode = container.querySelector('.animate-pulse')
    expect(pulsingNode).not.toBeNull()
  })

  it('shows all four step numbers', () => {
    render(
      <ModuleProgress
        completionStatus={{ M1: false, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M1}
      />,
    )
    expect(screen.getByText('1')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
    expect(screen.getByText('4')).toBeTruthy()
  })

  it('renders all four module labels', () => {
    render(
      <ModuleProgress
        completionStatus={{ M1: false, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M1}
      />,
    )
    expect(screen.getByText('Property')).toBeTruthy()
    expect(screen.getByText('Lifestyle')).toBeTruthy()
    expect(screen.getByText('Location')).toBeTruthy()
    expect(screen.getByText('Budget')).toBeTruthy()
  })

  it('does not apply animate-pulse to a completed module', () => {
    const { container } = render(
      <ModuleProgress
        completionStatus={{ M1: true, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M2}
      />,
    )
    const step1 = container.querySelector('#module-step-1')
    expect(step1?.querySelector('.animate-pulse')).toBeNull()
  })
})
