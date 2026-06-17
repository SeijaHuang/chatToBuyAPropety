'use client'

import React from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { MaterialSymbol } from '@/components/shared'

const NAV_TABS = [
  { label: 'Home',    icon: 'home',     path: '/'        },
  { label: 'Search',  icon: 'search',   path: '/search'  },
  { label: 'Saved',   icon: 'bookmark', path: '/saved'   },
  { label: 'Profile', icon: 'person',   path: '/profile' },
] as const

export function BottomNavBar(): React.ReactElement {
  const pathname: string = usePathname()
  const router = useRouter()

  return (
    <nav
      className={cn(
        'md:hidden fixed bottom-0 left-0 right-0',
        'flex items-center justify-around',
        'h-16',
        'bg-surface border-t border-outline-variant',
        'z-20',
      )}
    >
      {NAV_TABS.map((tab) => {
        const isActive: boolean = pathname === tab.path
        return (
          <button
            key={tab.path}
            onClick={() => router.push(tab.path)}
            className={cn(
              'flex flex-col items-center justify-center gap-[2px]',
              'flex-1 h-full',
              'transition-colors',
              isActive ? 'text-primary' : 'text-outline',
            )}
          >
            <MaterialSymbol name={tab.icon} filled={isActive} />
            <span className="text-caption">{tab.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
