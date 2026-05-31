import React from 'react'
import { tv } from '@/lib/tv'

const moduleStep = tv({
  slots: {
    root: 'flex flex-col items-center gap-xs',
    circle:
      'inline-flex items-center justify-center p-[6px] aspect-square rounded-full border-2 transition-colors',
    icon: 'text-label-lg',
    label: 'text-label-md',
  },
  variants: {
    status: {
      completed: {
        circle: 'bg-primary-container border-primary-container',
        icon: 'text-on-primary-container',
        label: 'text-primary-container',
      },
      active: {
        circle: 'bg-transparent border-primary-container animate-pulse',
        icon: 'text-primary-container',
        label: 'text-on-surface',
      },
      pending: {
        circle: 'bg-transparent border-outline-variant',
        icon: 'text-outline-variant',
        label: 'text-outline-variant',
      },
    },
  },
})

export type StepStatus = 'completed' | 'active' | 'pending'

export interface StepProps {
  label: string
  step: number
  status: StepStatus
}

export function ModuleStep({ label, step, status }: StepProps): React.ReactElement {
  const { root, circle, icon: iconSlot, label: labelSlot } = moduleStep({ status })

  return (
    <div className={root()}>
      <div className={circle()}>
        <span className={iconSlot()}>{step}</span>
      </div>
      <span className={labelSlot()}>{label}</span>
    </div>
  )
}
