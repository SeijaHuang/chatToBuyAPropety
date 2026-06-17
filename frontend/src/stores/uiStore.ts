import { create } from 'zustand'

interface UIStore {
  sidebarCollapsed: boolean
  activeModal: string | null

  toggleSidebar(): void
  setSidebarCollapsed(v: boolean): void
  openModal(id: string): void
  closeModal(): void
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarCollapsed: false,
  activeModal: null,

  toggleSidebar(): void {
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed }))
  },

  setSidebarCollapsed(v: boolean): void {
    set({ sidebarCollapsed: v })
  },

  openModal(id: string): void {
    set({ activeModal: id })
  },

  closeModal(): void {
    set({ activeModal: null })
  },
}))
