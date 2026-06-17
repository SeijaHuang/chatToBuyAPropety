'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { tv } from '@/lib/tv'
import { cn } from '@/lib/utils'
import { MaterialSymbol } from '@/components/shared'
import { Button } from '@/components/shared'
import { useConversationStore } from '@/stores'
import { STORAGE_KEY } from '@/constants/storageKeys'
import { MESSAGE_ROLE } from '@/constants'
import type { ConversationStateDTO } from '@/types'

const sidebar = tv({
  base: 'hidden md:flex flex-col h-screen fixed top-0 left-0 bg-surface-container-low border-r border-outline-variant transition-all duration-300 ease-in-out overflow-hidden',
  variants: {
    collapsed: {
      false: 'w-sidebar-expanded',
      true: 'w-sidebar-collapsed',
    },
  },
  defaultVariants: { collapsed: false },
})

interface SideNavBarProps {
  collapsed: boolean
  onToggleCollapse(): void
  activePath: string
}

interface SessionHistoryItem {
  sessionId: string
  preview: string
  timestamp: string
}

export function SideNavBar({
  collapsed,
  onToggleCollapse,
  activePath,
}: SideNavBarProps): React.ReactElement {
  const router = useRouter()
  const clearSession = useConversationStore((s) => s.clearSession)
  const [sessions, setSessions] = useState<SessionHistoryItem[]>([])

  useEffect(() => {
    const items: SessionHistoryItem[] = []
    for (let i: number = 0; i < sessionStorage.length; i++) {
      const key: string | null = sessionStorage.key(i)
      if (key === null) continue
      if (!key.startsWith(STORAGE_KEY.CONVERSATION_STATE_PREFIX)) continue

      const sessionId: string = key.slice(STORAGE_KEY.CONVERSATION_STATE_PREFIX.length)
      const raw: string | null = sessionStorage.getItem(key)
      if (raw === null) continue

      const parsed: ConversationStateDTO = JSON.parse(raw) as ConversationStateDTO
      const firstUserMsg = parsed.conversationHistory.find(
        (entry) => entry.role === MESSAGE_ROLE.USER
      )
      if (firstUserMsg === undefined) continue

      const preview: string = firstUserMsg.content.slice(0, 30)
      if (preview.length === 0) continue

      items.push({ sessionId, preview, timestamp: 'recent' })
      if (items.length >= 10) break
    }
    setSessions(items)
  }, [])

  const handleNewChat = (): void => {
    clearSession()
    router.push('/')
  }

  return (
    <aside className={sidebar({ collapsed })}>
      {/* Header */}
      <div className={cn('flex items-center justify-between', 'h-14 px-sm')}>
        <div className={cn('flex items-center gap-xs overflow-hidden')}>
          <MaterialSymbol name="auto_awesome" filled className="text-[--color-primary] shrink-0" />
          <span
            className={cn(
              'text-title-lg font-semibold text-on-surface whitespace-nowrap',
              'transition-opacity duration-150',
              collapsed ? 'opacity-0 delay-0' : 'opacity-100 delay-300'
            )}
          >
            Homi AI
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={collapsed ? 'left_panel_open' : 'left_panel_close'}
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        />
      </div>

      {/* New Chat */}
      <div className={cn('px-sm pb-sm', collapsed && 'flex justify-center')}>
        <Button
          variant="secondary"
          icon="add"
          onClick={handleNewChat}
          aria-label="New Chat"
          className={cn(!collapsed && 'w-full')}
        >
          {!collapsed && 'New Chat'}
        </Button>
      </div>

      {/* Navigation */}
      <nav className={cn('flex flex-col gap-sm', 'px-sm')}>
        {/* Home */}
        <Button
          variant={activePath === '/' ? 'primary' : 'ghost'}
          size="md"
          icon="home"
          onClick={() => router.push('/')}
          className={cn(
            !collapsed && 'w-full justify-start',
            activePath !== '/' && 'text-on-surface-variant hover:bg-surface-variant'
          )}
        >
          {!collapsed && 'Home'}
        </Button>

        {/* Search — disabled */}
        <Button
          variant="ghost"
          size="md"
          icon="search"
          disabled
          title="Coming in next release"
          className={cn(!collapsed && 'w-full justify-start', 'text-on-surface-variant')}
        >
          {!collapsed && 'Search'}
        </Button>
      </nav>

      {/* Session history — expanded only */}
      {!collapsed && (
        <div className={cn('flex flex-col', 'mt-md px-sm', 'flex-1 overflow-y-auto')}>
          <p className="text-label-md text-outline px-sm mb-xs">Recent</p>
          {sessions.map((item: SessionHistoryItem) => {
            const isActive: boolean = activePath === `/chat/${item.sessionId}`
            return (
              <Button
                key={item.sessionId}
                variant={isActive ? 'primary' : 'ghost'}
                onClick={() => router.push(`/chat/${item.sessionId}`)}
                className={cn(
                  'h-auto flex-col items-start justify-start',
                  'w-full px-sm py-xs rounded-xl',
                  'text-left',
                  !isActive && 'text-on-surface-variant hover:bg-surface-variant'
                )}
              >
                <span className="text-label-md truncate w-full">{item.preview}</span>
                <span className="text-caption text-outline">{item.timestamp}</span>
              </Button>
            )
          })}
        </div>
      )}
    </aside>
  )
}
