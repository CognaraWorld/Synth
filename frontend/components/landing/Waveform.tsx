'use client'

import { motion } from 'framer-motion'

interface WaveformProps {
  active?: boolean
  bars?: number
  color?: string
  className?: string
}

export function Waveform({
  active = false,
  bars = 24,
  color = '#0D9488',
  className = '',
}: WaveformProps) {
  return (
    <div className={`flex items-center justify-center gap-[2px] h-6 ${className}`}>
      {Array.from({ length: bars }).map((_, i) => (
        <motion.div
          key={i}
          className="w-[3px] rounded-full"
          style={{ backgroundColor: color }}
          animate={
            active
              ? {
                  height: [3, 8 + Math.random() * 16, 3],
                }
              : { height: 3 }
          }
          transition={
            active
              ? {
                  duration: 0.4 + Math.random() * 0.4,
                  repeat: Infinity,
                  repeatType: 'reverse',
                  delay: i * 0.03,
                  ease: 'easeInOut',
                }
              : { duration: 0.3 }
          }
        />
      ))}
    </div>
  )
}
