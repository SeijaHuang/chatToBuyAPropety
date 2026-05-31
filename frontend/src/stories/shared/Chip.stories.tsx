import type { Story } from '@ladle/react'
import { Chip } from '@/components/shared'

export const Colors: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Chip label="Neutral" color="neutral" />
    <Chip label="Primary" color="primary" />
    <Chip label="Tertiary" color="tertiary" />
    <Chip label="Error" color="error" />
  </div>
)

export const WithIcon: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Chip label="Bedroom" icon="bed" color="primary" />
    <Chip label="Investment" icon="trending_up" color="tertiary" />
    <Chip label="Overbudget" icon="warning" color="error" />
  </div>
)

export const WithRemove: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Chip label="Removable" onRemove={() => {}} />
    <Chip label="With Icon" icon="home" color="primary" onRemove={() => {}} />
  </div>
)
