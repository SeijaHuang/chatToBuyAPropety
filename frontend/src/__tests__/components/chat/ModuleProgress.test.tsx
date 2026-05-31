import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ModuleProgress } from '@/components/chat/ModuleProgress'
import { MODULE_ID } from '@/constants'

describe('ModuleProgress', () => {
  it('shows check icon when module is completed', () => {
    render(
      <ModuleProgress
        completionStatus={{ M1: true, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M2}
      />,
    )
    expect(screen.getByText('check')).toBeTruthy()
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

  it('does not show check icon for pending module', () => {
    render(
      <ModuleProgress
        completionStatus={{ M1: false, M2: false, M3: false, M4: false }}
        currentModule={MODULE_ID.M1}
      />,
    )
    expect(screen.queryByText('check')).toBeNull()
  })
})
