'use client'

import { useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger)

interface ScrollRevealProps {
  children: React.ReactNode
  direction?: 'up' | 'down' | 'left' | 'right'
  delay?: number
  stagger?: number
  className?: string
}

export function ScrollReveal({
  children,
  direction = 'up',
  delay = 0,
  stagger = 0.1,
  className = '',
}: ScrollRevealProps) {
  const container = useRef<HTMLDivElement>(null)

  const directionMap = {
    up: { y: 40 },
    down: { y: -40 },
    left: { x: 40 },
    right: { x: -40 },
  }

  useGSAP(() => {
    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches

    if (prefersReducedMotion) return

    const elements = container.current?.children
    if (!elements) return

    gsap.from(elements, {
      ...directionMap[direction],
      opacity: 0,
      duration: 0.8,
      delay,
      stagger,
      ease: 'power2.out',
      scrollTrigger: {
        trigger: container.current,
        start: 'top 85%',
        toggleActions: 'play none none none',
      },
    })
  }, { scope: container })

  return (
    <div ref={container} className={className}>
      {children}
    </div>
  )
}
