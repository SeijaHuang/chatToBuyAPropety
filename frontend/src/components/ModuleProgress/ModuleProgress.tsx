'use client'

import React from 'react'
import { cn } from '@/lib/utils'
import { MODULE_ID } from '@/constants'
import type { ModuleID } from '@/types'
import { ModuleStep } from './ModuleStep'
import type { StepStatus } from './ModuleStep'

type ModuleKey = 'M1' | 'M2' | 'M3' | 'M4'

const MODULES = [
  { key: 'M1' as const, id: MODULE_ID.M1, label: 'Property', step: 1 },
  { key: 'M2' as const, id: MODULE_ID.M2, label: 'Lifestyle', step: 2 },
  { key: 'M3' as const, id: MODULE_ID.M3, label: 'Location', step: 3 },
  { key: 'M4' as const, id: MODULE_ID.M4, label: 'Budget', step: 4 },
] as const

interface ModuleProgressProps {
  completionStatus: { M1: boolean; M2: boolean; M3: boolean; M4: boolean }
  currentModule: ModuleID
}

export function ModuleProgress({
  completionStatus,
  currentModule,
}: ModuleProgressProps): React.ReactElement {
  return (
    <div className={cn('flex items-center', 'sticky top-0 z-10', 'bg-surface px-md py-sm')}>
      {MODULES.map((module, index) => {
        const isCompleted: boolean = completionStatus[module.key as ModuleKey]
        const isCurrent: boolean = module.id === currentModule && !isCompleted
        const status: StepStatus = isCompleted ? 'completed' : isCurrent ? 'active' : 'pending'

        return (
          <React.Fragment key={module.key}>
            <ModuleStep label={module.label} step={module.step} status={status} />
            {index < MODULES.length - 1 && (
              <div
                className={cn(
                  'flex-1 h-px mx-sm',
                  isCompleted ? 'bg-primary-container' : 'bg-outline-variant'
                )}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
