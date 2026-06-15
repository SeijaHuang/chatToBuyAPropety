'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { v4 as uuid } from 'uuid'
import { Button } from '@/components/shared'

export function NewSessionButton(): React.ReactElement {
  const router = useRouter()

  const handleStart = (): void => {
    const sessionId: string = uuid()
    router.push(`/chat/${sessionId}`)
  }

  return (
    <Button variant="primary" onClick={handleStart}>
      Start conversation
    </Button>
  )
}
