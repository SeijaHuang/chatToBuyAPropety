import React from 'react'
import { NewSessionButton } from './_components/NewSessionButton'

export default function HomePage(): React.ReactElement {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-lg px-md">
      <h1 className="text-display-sm text-on-surface font-semibold">PropertyAI</h1>
      <p className="text-body-lg text-on-surface-variant">
        Your AI-powered property buying assistant
      </p>
      <NewSessionButton />
    </main>
  )
}
