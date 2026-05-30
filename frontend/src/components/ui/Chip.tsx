'use client'

import { tv } from '@/lib/tv'
import { MaterialSymbol } from '@/components/icons'
import type { ComponentColor } from '@/types'

const chip = tv({
  base: 'inline-flex items-center gap-xs rounded-full px-sm py-xs text-label-md',
  variants: {
    color: {
      primary:  'bg-primary/10 text-primary',
      tertiary: 'bg-tertiary/10 text-tertiary',
      error:    'bg-error/10 text-error',
      neutral:  'bg-on-surface/10 text-on-surface-variant',
    },
  },
  defaultVariants: {
    color: 'neutral',
  },
})

interface ChipProps {
  label: string
  color?: ComponentColor
  icon?: string
  onRemove?: () => void
}

export function Chip({ label, color = 'neutral', icon, onRemove }: ChipProps) {
  return (
    <div className={chip({ color })}>
      {icon && <MaterialSymbol name={icon} className="text-label-lg" />}
      <span>{label}</span>
      {onRemove && (
        <button
          onClick={onRemove}
          aria-label={`Remove ${label}`}
          className="ml-xs hover:opacity-70 transition-opacity"
        >
          <MaterialSymbol name="close" className="text-label-lg" />
        </button>
      )}
    </div>
  )
}
