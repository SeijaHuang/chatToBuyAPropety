import type { Story } from '@ladle/react'
import { SkeletonText, SkeletonMessage } from '../components/ui/Skeleton'

export const Text: Story = () => (
  <div className="flex flex-col gap-sm w-80">
    <SkeletonText />
    <SkeletonText width="w-3/4" />
    <SkeletonText width="w-1/2" />
  </div>
)

export const Message: Story = () => (
  <div className="flex flex-col gap-md w-96">
    <SkeletonMessage />
    <SkeletonMessage />
  </div>
)
