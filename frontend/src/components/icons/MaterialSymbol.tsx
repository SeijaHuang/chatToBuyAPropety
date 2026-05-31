'use client'

import { cn } from '@/lib/utils'

interface MaterialSymbolProps {
  name: string
  filled?: boolean
  className?: string
}

export function MaterialSymbol({ name, filled = false, className }: MaterialSymbolProps) {
  return (
    <span
      className={cn('material-symbols-outlined', filled && 'material-symbols-filled', className)}
      aria-hidden="true"
    >
      {name}
    </span>
  )
}
