import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '@/stores/uiStore'

beforeEach(() => {
  useUIStore.setState({ sidebarCollapsed: false, activeModal: null })
})

describe('uiStore', () => {
  describe('sidebarCollapsed', () => {
    it('is false by default', () => {
      expect(useUIStore.getState().sidebarCollapsed).toBe(false)
    })
  })

  describe('toggleSidebar', () => {
    it('flips false to true', () => {
      useUIStore.getState().toggleSidebar()
      expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    })

    it('flips true back to false', () => {
      useUIStore.setState({ sidebarCollapsed: true })
      useUIStore.getState().toggleSidebar()
      expect(useUIStore.getState().sidebarCollapsed).toBe(false)
    })
  })

  describe('setSidebarCollapsed', () => {
    it('sets the value directly', () => {
      useUIStore.getState().setSidebarCollapsed(true)
      expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    })
  })

  describe('openModal', () => {
    it('sets activeModal to the given id', () => {
      useUIStore.getState().openModal('settings')
      expect(useUIStore.getState().activeModal).toBe('settings')
    })
  })

  describe('closeModal', () => {
    it('resets activeModal to null', () => {
      useUIStore.setState({ activeModal: 'settings' })
      useUIStore.getState().closeModal()
      expect(useUIStore.getState().activeModal).toBeNull()
    })
  })
})
