import type { Story } from '@ladle/react'
import { AIBadge } from '@/components/shared'

export const Small: Story = () => <AIBadge size="sm" />
Small.storyName = 'Small (default)'

export const Medium: Story = () => <AIBadge size="md" />

export const CustomLabel: Story = () => (
  <div className="flex flex-col gap-sm">
    <AIBadge size="sm" label="Powered by AI" />
    <AIBadge size="md" label="Powered by AI" />
  </div>
)
