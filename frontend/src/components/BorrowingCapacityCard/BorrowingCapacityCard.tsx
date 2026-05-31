'use client'

import { cn, formatAUD } from '@/lib/utils'
import { MaterialSymbol } from '@/components/shared'
import type { BorrowingCapacityResult } from '@/types'

interface BorrowingCapacityCardProps {
  data: BorrowingCapacityResult
}

export function BorrowingCapacityCard({ data }: BorrowingCapacityCardProps): React.ReactElement {
  return (
    <div
      className={cn(
        'glass-panel rounded-xl',
        'flex flex-col',
        'p-md gap-sm',
      )}
    >
      <div className={cn('flex items-center', 'gap-xs')}>
        <MaterialSymbol name="auto_awesome" filled className="text-tertiary-container" />
        <span className="text-label-lg text-on-surface-variant">Borrowing Estimate</span>
      </div>

      <p className="text-headline-md text-on-surface">
        {formatAUD(data.estimated_capacity)}
      </p>

      <div className={cn('flex items-center flex-wrap', 'gap-sm', 'text-body-md text-on-surface-variant')}>
        <span>{formatAUD(data.monthly_repayment)}/mo</span>
        <span>{data.annual_rate.toFixed(2)}% p.a.</span>
        <span>{data.loan_term_years} years</span>
      </div>

      <p className="text-caption text-on-surface-variant">
        {data.disclaimer}
      </p>
    </div>
  )
}
