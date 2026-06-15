'use client'

import React from 'react'
import { cn, formatAUD } from '@/lib/utils'
import { MaterialSymbol, Chip } from '@/components/shared'
import type { BudgetGapResult } from '@/types'

interface BudgetGapCardProps {
  data: BudgetGapResult
}

export function BudgetGapCard({ data }: BudgetGapCardProps): React.ReactElement | null {
  if (!data.has_gap) return null

  return (
    <div
      className={cn(
        'glass-panel rounded-xl',
        'flex flex-col',
        'p-md gap-sm',
      )}
    >
      <div className={cn('flex items-center', 'gap-xs')}>
        <MaterialSymbol name="warning" className="text-error" />
        <span className="text-label-lg text-on-surface">Budget Gap Detected</span>
      </div>

      <div className={cn('flex flex-col', 'gap-xs', 'text-body-md text-on-surface-variant')}>
        <span>Your budget: {formatAUD(data.budget_max)}</span>
        <span>Market median ({data.reference_suburb}): {formatAUD(data.market_median)}</span>
        <span>Gap: {data.gap_percentage.toFixed(1)}%</span>
      </div>

      <div className={cn('flex flex-wrap', 'gap-xs')}>
        {data.suggested_actions.map((action: string) => (
          <Chip key={action} label={action} color="neutral" />
        ))}
      </div>
    </div>
  )
}
