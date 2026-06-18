import React from 'react'
import { cn } from '@/lib/utils'
import { MaterialSymbol } from '@/components/shared'

export function TopNavBar(): React.ReactElement {
  return (
    <header
      id="top-nav-bar"
      className={cn(
        'md:hidden flex',
        'items-center justify-between',
        'h-14 px-md',
        'bg-surface border-b border-outline-variant',
        'sticky top-0 z-20'
      )}
    >
      <div className={cn('flex items-center gap-xs')}>
        <MaterialSymbol name="auto_awesome" filled className="text-[--color-primary]" />
        <span className="text-title-lg font-semibold text-on-surface">Homi AI</span>
      </div>
      <div className={cn('flex items-center gap-sm')}>
        <MaterialSymbol name="notifications" className="text-on-surface-variant" />
        <div className="w-8 h-8 rounded-full bg-surface-container-high" />
      </div>
    </header>
  )
}
