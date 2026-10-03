import type { ButtonHTMLAttributes } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover',
  secondary: 'bg-surface-raised text-text border border-border hover:border-accent',
  danger: 'bg-danger/10 text-danger border border-danger/40 hover:bg-danger/20',
  ghost: 'bg-transparent text-text-dim hover:text-text hover:bg-surface-raised',
}

export function buttonClasses(variant: ButtonVariant = 'primary', className = ''): string {
  return `inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`
}

type NativeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  'onDrag' | 'onDragStart' | 'onDragEnd' | 'onAnimationStart' | 'onAnimationEnd'
>

interface ButtonProps extends NativeButtonProps {
  variant?: ButtonVariant
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  const prefersReducedMotion = useReducedMotion()
  return (
    <motion.button
      whileHover={prefersReducedMotion || props.disabled ? undefined : { scale: 1.03 }}
      whileTap={prefersReducedMotion || props.disabled ? undefined : { scale: 0.97 }}
      transition={{ duration: 0.12 }}
      className={buttonClasses(variant, className)}
      {...props}
    />
  )
}
