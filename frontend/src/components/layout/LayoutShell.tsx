'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores'
import { SideNavBar } from './SideNavBar'
import { TopNavBar } from './TopNavBar'
import { BottomNavBar } from './BottomNavBar'

interface LayoutShellProps {
  children: React.ReactNode
}

export function LayoutShell({ children }: LayoutShellProps): React.ReactElement {
  const sidebarCollapsed: boolean = useUIStore((s) => s.sidebarCollapsed)
  const toggleSidebar: () => void = useUIStore((s) => s.toggleSidebar)
  const pathname: string = usePathname()

  return (
    <div className="flex min-h-screen bg-surface text-on-surface">
      <SideNavBar
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
        activePath={pathname}
      />
      <div
        className={cn(
          'flex flex-col flex-1 min-w-0',
          'transition-all duration-300 ease-in-out',
          sidebarCollapsed ? 'md:ml-sidebar-collapsed' : 'md:ml-sidebar-expanded',
        )}
      >
        <TopNavBar />
        <main className="flex-1">{children}</main>
        <BottomNavBar />
      </div>
    </div>
  )
}
