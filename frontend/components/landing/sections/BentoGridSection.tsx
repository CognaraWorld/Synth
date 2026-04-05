'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect } from 'react'
import { FileText, Globe, Users, Brain, Upload, Search, CheckCircle, ArrowRight } from 'lucide-react'

const ease = [0.16, 1, 0.3, 1] as const

const cardVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: i * 0.1, ease },
  }),
}

/* ── Document Intelligence Card ── */
function DocCard() {
  const [phase, setPhase] = useState(0) // 0=idle, 1=scanning, 2=answer

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 1500)
    const t2 = setTimeout(() => setPhase(2), 3200)
    const t3 = setTimeout(() => setPhase(0), 7000)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-[#EFF6FF] flex items-center justify-center">
          <FileText size={18} className="text-[#2563EB]" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-[#1D1D1F]">Document Intelligence</h3>
          <p className="text-sm text-[#6E6E73]">PDFs, contracts, slide decks</p>
        </div>
      </div>

      <div className="rounded-xl border border-[#EAE8E4] bg-[#FAF9F6] p-4 space-y-3">
        {/* File */}
        <div className="flex items-center gap-2">
          <Upload size={12} className="text-[#86868B]" />
          <span className="text-sm text-[#6E6E73]">Q2_Budget.pdf</span>
          <motion.span
            className="text-[9px] text-accent-green/70 ml-auto"
            animate={{ opacity: phase >= 1 ? 1 : 0 }}
          >
            {phase >= 2 ? 'Indexed' : 'Scanning...'}
          </motion.span>
        </div>
        {/* Scan bar */}
        <div className="h-0.5 rounded-full bg-black/[0.04] overflow-hidden">
          <motion.div
            className="h-full bg-blue-400/50 rounded-full"
            animate={{ width: phase === 0 ? '0%' : phase === 1 ? '60%' : '100%' }}
            transition={{ duration: phase === 1 ? 1.5 : 0.5 }}
          />
        </div>
        {/* Answer */}
        <AnimatePresence>
          {phase >= 2 && (
            <motion.p
              className="text-xs text-[#6E6E73]"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <span className="text-warm-amber">Budget:</span> $120,000 across 3 phases
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

/* ── Web Grounding Card ── */
function WebCard() {
  const [phase, setPhase] = useState(0)

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 2000)
    const t2 = setTimeout(() => setPhase(2), 3800)
    const t3 = setTimeout(() => setPhase(0), 7500)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-accent-green/10 flex items-center justify-center">
          <Globe size={18} className="text-accent-green" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-[#1D1D1F]">Web Grounding</h3>
          <p className="text-sm text-[#6E6E73]">Live fact-checking</p>
        </div>
      </div>

      <div className="rounded-xl border border-[#EAE8E4] bg-[#FAF9F6] p-4 space-y-2.5">
        <p className="text-sm text-[#6E6E73] italic">&quot;Latest OpenAI valuation?&quot;</p>
        <AnimatePresence>
          {phase >= 1 && (
            <motion.div
              className="flex items-center gap-1.5"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <motion.div animate={{ rotate: phase === 1 ? 360 : 0 }} transition={{ duration: 1, repeat: phase === 1 ? Infinity : 0 }}>
                <Search size={10} className="text-accent-green/60" />
              </motion.div>
              <span className="text-[10px] text-[#86868B]">
                {phase === 1 ? 'Searching 3 sources...' : 'Verified'}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
        <AnimatePresence>
          {phase >= 2 && (
            <motion.div
              className="flex items-center gap-1.5"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <CheckCircle size={10} className="text-accent-green" />
              <span className="text-xs text-[#6E6E73]">
                <span className="font-semibold text-[#1D1D1F]">$300B</span> — Reuters, Mar 2025
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

/* ── Persona Switching Card ── */
const PERSONAS = [
  { label: 'Research Analyst', color: '#8B5CF6' },
  { label: 'Technical Architect', color: '#3B82F6' },
  { label: 'Sales Advisor', color: '#0D9488' },
]

function PersonaCard() {
  const [active, setActive] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => setActive((p) => (p + 1) % PERSONAS.length), 2500)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-ai-purple/10 flex items-center justify-center">
          <Users size={18} className="text-ai-purple" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-[#1D1D1F]">Persona Switching</h3>
          <p className="text-sm text-[#6E6E73]">Adapt to any role</p>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {PERSONAS.map((p, i) => (
          <motion.div
            key={p.label}
            className="flex items-center gap-3 px-4 py-3 rounded-lg border transition-colors"
            animate={{
              borderColor: i === active ? p.color + '30' : '#EAE8E4',
              backgroundColor: i === active ? p.color + '08' : '#FAF9F6',
            }}
            transition={{ duration: 0.4 }}
          >
            <motion.div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: p.color }}
              animate={{ scale: i === active ? [1, 1.3, 1] : 1 }}
              transition={{ duration: 0.6 }}
            />
            <span className={`text-sm font-medium ${i === active ? 'text-[#424245]' : 'text-[#86868B]'}`}>
              {p.label}
            </span>
            {i === active && (
              <motion.span
                className="text-[9px] ml-auto font-medium"
                style={{ color: p.color }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                Active
              </motion.span>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  )
}

/* ── Meeting Memory Card ── */
function MemoryCard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-warm-amber/10 flex items-center justify-center">
          <Brain size={18} className="text-warm-amber" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-[#1D1D1F]">Meeting Memory</h3>
          <p className="text-sm text-[#6E6E73]">Contextual recall</p>
        </div>
      </div>

      <div className="rounded-xl border border-[#EAE8E4] bg-[#FAF9F6] p-4 space-y-2.5">
        <p className="text-sm text-[#6E6E73] italic">&quot;What did Sarah say about the deadline last week?&quot;</p>
        <div className="flex items-start gap-2 mt-2">
          <ArrowRight size={10} className="text-warm-amber mt-0.5 flex-shrink-0" />
          <p className="text-sm text-[#6E6E73]">
            In the Apr 1 standup, Sarah said the agency deadline was{' '}
            <span className="text-warm-amber font-medium">May 7</span> but flagged review risk.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-1 h-1 rounded-full bg-black/[0.08]" />
          <span className="text-xs text-[#AEAEB2]">Sourced from 3 past meetings</span>
        </div>
      </div>
    </div>
  )
}

/* ── Bento Grid Section ── */
export function BentoGridSection() {
  return (
    <section className="py-20 md:py-28 lg:py-36 px-4 md:px-8 lg:px-12 relative overflow-hidden bg-white">
      {/* Section ambient */}
      <div
        className="absolute top-[20%] left-[5%] w-[500px] h-[400px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(37,99,235,0.02), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div
        className="absolute bottom-[10%] right-[5%] w-[400px] h-[400px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(175,82,222,0.015), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div className="max-w-7xl mx-auto relative z-[1]">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7, ease }}
        >
          <p className="text-base font-medium text-warm-amber tracking-widest uppercase mb-4">
            Capabilities
          </p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight">
            More than a meeting bot.
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {[DocCard, WebCard, PersonaCard, MemoryCard].map((Card, i) => (
            <motion.div
              key={i}
              custom={i}
              variants={cardVariants}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-60px' }}
              className="rounded-2xl border border-[#EAE8E4] bg-white p-7 md:p-8 transition-colors duration-300 hover:border-[#D5D5D2]"
              style={{ boxShadow: '0 1px 3px rgba(26, 21, 15, 0.04)' }}
            >
              <Card />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
