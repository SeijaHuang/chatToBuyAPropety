import React from 'react'
import { LayoutShell } from '@/components/layout'

export default function MainLayout({ children }: { children: React.ReactNode }): React.ReactElement {
  return <LayoutShell>{children}</LayoutShell>
}
