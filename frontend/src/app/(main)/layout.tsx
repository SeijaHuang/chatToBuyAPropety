import React from 'react'
import { cn } from '@/lib/utils'

export default function MainLayout({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <div className={cn('flex min-h-screen flex-col', 'bg-surface text-on-surface')}>
      <header className={cn('sticky top-0 z-20', 'flex items-center', 'h-14 px-md', 'bg-surface border-b border-outline-variant')}>
        <span className="text-title-lg font-semibold text-on-surface">PropertyAI</span>
      </header>
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  )
}
