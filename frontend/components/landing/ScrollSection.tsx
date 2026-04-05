'use client'

import { useRef, type ReactNode } from 'react'
import { useScroll, type MotionValue } from 'framer-motion'

interface ScrollSectionProps {
  children: (progress: MotionValue<number>) => ReactNode
  height?: string
  className?: string
  id?: string
}

export function ScrollSection({
  children,
  height = '200vh',
  className = '',
  id,
}: ScrollSectionProps) {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end end'],
  })

  return (
    <section ref={ref} style={{ height }} className={className} id={id}>
      <div className="sticky top-0 h-screen overflow-hidden flex items-center justify-center">
        {children(scrollYProgress)}
      </div>
    </section>
  )
}
