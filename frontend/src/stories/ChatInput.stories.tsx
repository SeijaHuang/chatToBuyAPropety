import type { Story } from '@ladle/react'
import { ChatInput } from '@/components/ChatInput'

export const Default: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatInput onSend={(msg) => console.log('sent:', msg)} isLoading={false} />
  </div>
)

export const Loading: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatInput onSend={(msg) => console.log('sent:', msg)} isLoading={true} />
  </div>
)

export const Disabled: Story = () => (
  <div className="p-md max-w-2xl">
    <ChatInput onSend={(msg) => console.log('sent:', msg)} isLoading={false} disabled={true} />
  </div>
)
