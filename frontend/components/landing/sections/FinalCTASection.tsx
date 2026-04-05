'use client'

import { motion } from 'framer-motion'
import { ArrowRight, Calendar } from 'lucide-react'
import Link from 'next/link'

export function FinalCTASection() {
  return (
    <section id="book-demo" className="py-24 md:py-32 lg:py-40 px-4 md:px-8 lg:px-10 relative overflow-hidden bg-white">
      <div className="max-w-3xl mx-auto text-center relative z-10">
        <motion.h2
          className="text-5xl md:text-6xl lg:text-7xl font-bold text-[#1D1D1F] leading-tight tracking-tight"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          Run Cognara in your <br />
          <span className="gradient-text">next meeting.</span>
        </motion.h2>

        <motion.p
          className="mt-7 text-xl text-[#424245] max-w-lg mx-auto"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7, delay: 0.1 }}
        >
          Set up in 60 seconds. No credit card required.
        </motion.p>

        <motion.div
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7, delay: 0.2 }}
        >
          <Link
            href="/onboarding"
            className="inline-flex items-center h-16 px-10 text-lg font-semibold text-white rounded-full bg-[#2563EB] hover:bg-[#1D4FD7] active:scale-[0.97] transition-all gap-2"
          >
            Start free trial
            <ArrowRight size={16} />
          </Link>
          <a
            href="mailto:hello@cognara.ai"
            className="inline-flex items-center h-16 px-10 text-lg font-medium text-[#424245] rounded-full border border-[#EAE8E4] hover:bg-black/[0.03] transition-all gap-2"
          >
            <Calendar size={16} className="text-warm-amber" />
            Book a demo
          </a>
        </motion.div>
      </div>

      {/* Background glow — richer */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[600px] opacity-[0.08] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 50% 40%, rgba(13,148,136,0.04), transparent 70%)' }}
        aria-hidden="true"
      />
      <div
        className="absolute top-[30%] left-[20%] w-[400px] h-[300px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(175,82,222,0.015), transparent 65%)', filter: 'blur(80px)' }}
        aria-hidden="true"
      />
    </section>
  )
}
