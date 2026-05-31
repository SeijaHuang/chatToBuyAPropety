import type { Story } from '@ladle/react'
import { Button } from '@/components/shared'

export const Variants: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Button variant="primary">Primary</Button>
    <Button variant="secondary">Secondary</Button>
    <Button variant="ghost">Ghost</Button>
    <Button variant="danger">Danger</Button>
  </div>
)

export const Sizes: Story = () => (
  <div className="flex flex-wrap items-center gap-sm">
    <Button size="sm">Small</Button>
    <Button size="md">Medium</Button>
    <Button size="lg">Large</Button>
  </div>
)

export const WithIcon: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Button icon="search">Search</Button>
    <Button icon="add" variant="primary">Add</Button>
    <Button icon="delete" variant="danger">Delete</Button>
  </div>
)

export const Loading: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Button loading>Loading…</Button>
    <Button loading variant="primary">Saving…</Button>
  </div>
)

export const Disabled: Story = () => (
  <div className="flex flex-wrap gap-sm">
    <Button disabled>Disabled</Button>
    <Button disabled variant="primary">Disabled Primary</Button>
  </div>
)
