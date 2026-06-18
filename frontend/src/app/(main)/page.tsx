'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { v4 as uuid } from 'uuid'
import { ChatInput } from '@/components'
import { MaterialSymbol } from '@/components/shared'

export default function HomePage(): React.ReactElement {
  const router: ReturnType<typeof useRouter> = useRouter()

  const handleFirstMessage = (message: string): void => {
    const sessionId: string = uuid()
    router.push(`/chat/${sessionId}?q=${encodeURIComponent(message)}`)
  }

  return (
    <main className="flex flex-col items-center justify-center h-screen px-md">
      <div className="flex flex-col items-center gap-lg w-full max-w-3xl">
        <MaterialSymbol name="auto_awesome" filled className="text-[64px] text-tertiary animate-pulse" />
        <h1 className="text-display-md text-on-surface text-center">How can I help you today?</h1>
        <div className="w-full">
          <ChatInput
            onSend={handleFirstMessage}
            isLoading={false}
            placeholder="Tell me what you're looking for..."
          />
        </div>
        <p className="text-caption text-outline text-center">
          Homi AI can make mistakes. Verify important property or financial information.
        </p>
      </div>
    </main>
  )
}
