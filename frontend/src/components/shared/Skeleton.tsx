import { cn } from '@/lib/utils'

interface SkeletonTextProps {
  width?: string
  className?: string
}

export function SkeletonText({ width, className }: SkeletonTextProps) {
  return (
    <div className={cn('animate-pulse bg-surface-container-high rounded h-xs', width, className)} />
  )
}

interface SkeletonMessageProps {
  className?: string
}

export function SkeletonMessage({ className }: SkeletonMessageProps) {
  return (
    <div className={cn('flex gap-sm', className)}>
      <div className="animate-pulse bg-surface-container-high rounded-full size-avatar-sm shrink-0" />
      <div className="flex-1 space-y-xs">
        <div className="animate-pulse bg-surface-container-high rounded h-xs w-3/4" />
        <div className="animate-pulse bg-surface-container-high rounded h-xs w-1/2" />
      </div>
    </div>
  )
}
