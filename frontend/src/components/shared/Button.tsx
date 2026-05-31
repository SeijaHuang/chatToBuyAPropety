'use client'

import React from 'react'
import { tv } from '@/lib/tv'
import { MaterialSymbol } from './MaterialSymbol'
import type { ComponentSize, ComponentVariant } from '@/types'

const button = tv({
  base: [
    'inline-flex items-center justify-center gap-xs',
    'rounded-full font-medium transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
  ],
  variants: {
    variant: {
      primary:   'bg-primary-container text-on-primary-container',
      secondary: 'border border-outline-variant/30 text-on-surface hover:bg-surface-variant',
      ghost:     'text-primary hover:bg-primary/10',
      danger:    'bg-error-container text-on-error-container',
    },
    size: {
      sm: 'h-sm px-sm text-label-md',
      md: 'h-md px-md text-label-lg',
      lg: 'h-lg px-lg text-body-lg',
    },
    isDisabled: {
      true: 'opacity-50 cursor-not-allowed',
    },
  },
  defaultVariants: {
    variant: 'secondary',
    size: 'md',
  },
})

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ComponentVariant
  size?: ComponentSize
  loading?: boolean
  icon?: string
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  onClick,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={button({ variant, size, isDisabled: loading || disabled, class: className })}
      disabled={loading || disabled}
      onClick={onClick}
      {...rest}
    >
      {loading ? (
        <span className="animate-spin size-4 border-2 border-current border-t-transparent rounded-full" />
      ) : icon ? (
        <MaterialSymbol name={icon} className="text-body-lg" />
      ) : null}
      {children}
    </button>
  )
}
