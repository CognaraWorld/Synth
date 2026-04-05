'use client'

import { motion } from 'framer-motion'
import { X, Check, Volume2, VolumeX, Hand, Mic } from 'lucide-react'

const LEGACY = [
  { icon: Volume2, text: 'Always recording' },
  { icon: Mic, text: 'Interrupts conversations' },
  { icon: X, text: 'Speaks randomly without context' },
  { icon: X, text: 'No document or web awareness' },
]

const COGNARA = [
  { icon: VolumeX, text: 'Stays muted by default' },
  { icon: Hand, text: 'Raises hand before speaking' },
  { icon: Check, text: 'Responds only when asked' },
  { icon: Check, text: 'Full context from docs + web' },
]

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
}

export function ComparisonSection() {
  return (
    <section className="py-20 md:py-28 lg:py-36 px-4 md:px-8 lg:px-12 relative overflow-hidden bg-white">
      {/* Section ambient */}
      <div
        className="absolute top-0 right-[5%] w-[500px] h-[400px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(37,99,235,0.02), transparent 65%)', filter: 'blur(80px)' }}
        aria-hidden="true"
      />
      <div
        className="absolute bottom-[10%] left-[5%] w-[400px] h-[300px] opacity-[0.05] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(13,148,136,0.03), transparent 65%)', filter: 'blur(80px)' }}
        aria-hidden="true"
      />
      <div className="max-w-6xl mx-auto relative z-[1]">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7 }}
        >
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight">
            The meeting bot your <br className="hidden md:block" />
            <span className="gradient-text">clients won&apos;t hate.</span>
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
          {/* Legacy bots */}
          <motion.div
            className="rounded-2xl border border-[#D63031]/10 bg-[#FFF5F5] p-7 md:p-10"
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
          >
            <p className="text-sm font-semibold text-[#86868B] uppercase tracking-widest mb-7">
              Legacy Meeting Bots
            </p>
            <div className="space-y-5">
              {LEGACY.map((item, i) => {
                const Icon = item.icon
                return (
                  <motion.div key={i} className="flex items-center gap-3" variants={itemVariants}>
                    <div className="w-10 h-10 rounded-lg bg-[#D63031]/10 flex items-center justify-center flex-shrink-0">
                      <Icon size={20} className="text-[#D63031]" />
                    </div>
                    <span className="text-base text-[#424245]">{item.text}</span>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>

          {/* Cognara */}
          <motion.div
            className="rounded-2xl border border-[#0D9488]/15 bg-[#F0FDFA] p-7 md:p-10 section-glow"
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
          >
            <p className="text-sm font-semibold text-warm-amber uppercase tracking-widest mb-7">
              Cognara
            </p>
            <div className="space-y-5">
              {COGNARA.map((item, i) => {
                const Icon = item.icon
                return (
                  <motion.div key={i} className="flex items-center gap-3" variants={itemVariants}>
                    <div className="w-10 h-10 rounded-lg bg-[#0D9488]/12 flex items-center justify-center flex-shrink-0">
                      <Icon size={20} className="text-warm-amber" />
                    </div>
                    <span className="text-base text-[#424245]">{item.text}</span>
                  </motion.div>
                )
              })}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
