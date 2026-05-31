import type { Story } from '@ladle/react'
import { ModuleProgress } from '@/components/ModuleProgress'
import { MODULE_ID } from '@/constants'

export const AllPending: Story = () => (
  <ModuleProgress
    completionStatus={{ M1: false, M2: false, M3: false, M4: false }}
    currentModule={MODULE_ID.M1}
  />
)

export const M1Current: Story = () => (
  <ModuleProgress
    completionStatus={{ M1: false, M2: false, M3: false, M4: false }}
    currentModule={MODULE_ID.M1}
  />
)

export const M1Complete_M2Current: Story = () => (
  <ModuleProgress
    completionStatus={{ M1: true, M2: false, M3: false, M4: false }}
    currentModule={MODULE_ID.M2}
  />
)

export const AllComplete: Story = () => (
  <ModuleProgress
    completionStatus={{ M1: true, M2: true, M3: true, M4: true }}
    currentModule={MODULE_ID.COMPLETE}
  />
)
