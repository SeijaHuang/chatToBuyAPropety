import { tv } from '@/lib/tv'
import { MaterialSymbol } from './MaterialSymbol'
import type { ComponentSize } from '@/types'

const aiBadge = tv({
  slots: {
    root:  'glass-ai inline-flex items-center gap-xs rounded-full',
    icon:  'text-tertiary-container',
    label: '',
  },
  variants: {
    size: {
      sm: { root: 'px-xs py-2xs',    icon: 'text-label-lg', label: 'text-label-md' },
      md: { root: 'px-sm py-xs',    icon: 'text-body-lg',  label: 'text-label-lg' },
    },
  },
  defaultVariants: {
    size: 'sm',
  },
})

type AIBadgeSize = Extract<ComponentSize, 'sm' | 'md'>

interface AIBadgeProps {
  label?: string
  size?: AIBadgeSize
}

export function AIBadge({ label = 'AI', size = 'sm' }: AIBadgeProps) {
  const { root, icon, label: labelClass } = aiBadge({ size })

  return (
    <span className={root()}>
      <MaterialSymbol name="auto_awesome" filled className={icon()} />
      <span className={labelClass()}>{label}</span>
    </span>
  )
}
