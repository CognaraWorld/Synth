'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight, Play, Hand, Shield } from 'lucide-react'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { MeetingWindow, Participant, ChatBubble } from '../MeetingWindow'
import { Waveform } from '../Waveform'

const ease = [0.16, 1, 0.3, 1] as const

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, delay: i * 0.12, ease },
  }),
}

/* ── Timed meeting demo sequence ── */
const DEMO_STEPS = [
  { at: 0, type: 'status', value: 'Cognara is listening...' },
  { at: 800, type: 'msg', from: 'Alex', color: '#3B82F6', text: "What's the status of the launch?" },
  { at: 2200, type: 'msg', from: 'Sarah', color: '#8B5CF6', text: 'Marketing assets are delayed. Waiting on creative review.' },
  { at: 4000, type: 'msg', from: 'Alex', color: '#3B82F6', text: 'Hey Cognara, summarize the risks.' },
  { at: 5200, type: 'hand' },
  { at: 6000, type: 'status', value: 'Cognara is speaking...' },
  { at: 6200, type: 'speaking' },
  { at: 6800, type: 'bullet', text: 'Marketing delay — creative review pending' },
  { at: 7600, type: 'bullet', text: 'QA incomplete — 3 test suites failing' },
  { at: 8400, type: 'bullet', text: 'Launch may slip 1 week to May 14' },
  { at: 9800, type: 'status', value: 'Cognara is listening...' },
  { at: 10000, type: 'done' },
] as const

function HeroMeetingDemo() {
  const [msgs, setMsgs] = useState<Array<{ from: string; color: string; text: string }>>([])
  const [bullets, setBullets] = useState<string[]>([])
  const [status, setStatus] = useState('Cognara is listening...')
  const [handRaised, setHandRaised] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [showResponse, setShowResponse] = useState(false)

  useEffect(() => {
    const timers: NodeJS.Timeout[] = []

    for (const step of DEMO_STEPS) {
      timers.push(
        setTimeout(() => {
          switch (step.type) {
            case 'status':
              setStatus(step.value)
              if (step.value === 'Cognara is listening...') {
                setSpeaking(false)
                setHandRaised(false)
              }
              break
            case 'msg':
              setMsgs((p) => [...p, { from: step.from, color: step.color, text: step.text }])
              break
            case 'hand':
              setHandRaised(true)
              setShowResponse(true)
              break
            case 'speaking':
              setSpeaking(true)
              break
            case 'bullet':
              setBullets((p) => [...p, step.text])
              break
            case 'done':
              // Loop after pause
              setTimeout(() => {
                setMsgs([])
                setBullets([])
                setShowResponse(false)
                setSpeaking(false)
                setHandRaised(false)
                setStatus('Cognara is listening...')
                // Re-trigger by re-mounting would be complex; just let it stay at end state
              }, 3000)
              break
          }
        }, step.at + 1200) // 1.2s initial delay for page entrance
      )
    }

    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <MeetingWindow title="Q2 Planning Standup" status={status}>
      {/* Participants */}
      <div className="flex items-center justify-center gap-5 md:gap-7 mb-5">
        <Participant
          name="Alex"
          initials="AK"
          color="#3B82F6"
          speaking={msgs.length > 0 && msgs.length < 3 && !speaking}
        />
        <Participant name="Sarah" initials="SL" color="#8B5CF6" />
        <div className="relative">
          <Participant name="Cognara" initials="C" color="#0D9488" ai speaking={speaking} />
          {/* Hand raise overlay */}
          <AnimatePresence>
            {handRaised && !speaking && (
              <motion.div
                className="absolute -top-3 -right-3 flex h-7 w-7 items-center justify-center rounded-full border border-[#0D9488]/15 bg-[#F0FDFA] shadow-sm shadow-[rgba(26,21,15,0.04)]"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 15 }}
              >
                <Hand size={14} className="text-warm-amber" />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Waveform */}
      <div className="flex justify-center mb-4 h-6">
        <Waveform active={speaking || (msgs.length > 0 && msgs.length < 3)} bars={28} />
      </div>

      {/* Transcript */}
      <div className="min-h-[200px] max-h-[260px] overflow-hidden space-y-4 border-t border-[#EAE8E4] pt-4">
        <p className="text-xs font-medium uppercase tracking-widest text-[#86868B]">
          Transcript
        </p>

        <AnimatePresence>
          {msgs.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease }}
            >
              <ChatBubble name={msg.from} color={msg.color} message={msg.text} />
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Cognara response */}
        <AnimatePresence>
          {showResponse && bullets.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease }}
              className="rounded-xl border border-[#0D9488]/15 bg-[#F0FDFA] p-4"
            >
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-sm font-bold text-warm-amber">Cognara</span>
              </div>
              <div className="space-y-1.5">
                {bullets.map((b, i) => (
                  <motion.div
                    key={i}
                    className="flex items-start gap-2"
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.05, ease }}
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-warm-amber mt-2 flex-shrink-0" />
                    <span className="text-sm text-[#424245]">{b}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MeetingWindow>
  )
}

/* ── Trust strip ── */
const PLATFORMS = [
  { name: 'Zoom', color: '#2D8CFF' },
  { name: 'Microsoft Teams', color: '#6264A7' },
  { name: 'Google Meet', color: '#00897B' },
]

function TrustStrip() {
  return (
    <motion.div
      className="mt-16 md:mt-20 flex flex-col items-center gap-5"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay: 1.2, ease }}
    >
      <div className="flex flex-wrap items-center justify-center gap-6 md:gap-10">
        <span className="text-xs font-medium uppercase tracking-widest text-[#86868B]">
          Works with
        </span>
        {PLATFORMS.map((p) => (
          <div key={p.name} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-base font-medium text-[#6E6E73]">{p.name}</span>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Shield size={12} className="text-[#AEAEB2]" />
        <span className="text-sm font-medium text-[#86868B]">
          Privacy-first AI powered by Whisper and Kokoro
        </span>
      </div>
    </motion.div>
  )
}

/* ── Hero Section ── */
export function HeroSection() {
  return (
    <section className="relative flex min-h-screen flex-col justify-center overflow-hidden bg-[#FAF9F6] pt-20 pb-8">
      <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          {/* Left */}
          <div className="z-10 order-2 lg:order-1">
            <motion.div
              custom={0} variants={fadeUp} initial="hidden" animate="visible"
              className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#0D9488]/15 bg-[#F0FDFA] px-3 py-1.5"
            >
              <span className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
              <span className="text-xs font-medium text-warm-amber tracking-wide uppercase">Now in Beta</span>
            </motion.div>

            <motion.h1
              custom={1} variants={fadeUp} initial="hidden" animate="visible"
              className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold leading-[1.04] tracking-tight text-[#1D1D1F]"
            >
              The AI teammate that knows{' '}
              <span className="gradient-text">when to speak.</span>
            </motion.h1>

            <motion.p
              custom={2} variants={fadeUp} initial="hidden" animate="visible"
              className="mt-7 max-w-xl text-xl leading-relaxed text-[#424245] md:text-2xl"
            >
              Cognara joins your meetings, listens, researches, and responds — only when asked.
            </motion.p>

            <motion.div
              custom={3} variants={fadeUp} initial="hidden" animate="visible"
              className="mt-10 flex flex-wrap items-center gap-5"
            >
              <Link
                href="/onboarding"
                className="inline-flex h-14 items-center gap-2.5 rounded-full bg-[#2563EB] px-8 text-base font-semibold text-white transition-all active:scale-[0.97] hover:bg-[#1D4FD7] md:h-16 md:px-10 md:text-lg"
              >
                Start free trial <ArrowRight size={18} />
              </Link>
              <a
                href="#demo"
                className="inline-flex h-14 items-center gap-2.5 rounded-full border border-[#EAE8E4] px-8 text-base font-medium text-[#424245] transition-all hover:bg-black/[0.03] md:h-16 md:px-10 md:text-lg"
              >
                <Play size={14} className="text-warm-amber" /> Watch demo
              </a>
            </motion.div>
          </div>

          {/* Right — Animated meeting micro-demo */}
          <motion.div
            className="order-1 lg:order-2"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 1, delay: 0.4, ease }}
          >
            <HeroMeetingDemo />
          </motion.div>
        </div>

        <TrustStrip />
      </div>

      {/* Background glow — two-layer */}
      <div
        className="pointer-events-none absolute top-1/3 left-1/2 h-[700px] w-[1000px] -translate-x-1/2 -translate-y-1/2"
        style={{ background: 'radial-gradient(ellipse 60% 50%, rgba(13,148,136,0.03), transparent 70%)' }}
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute top-[60%] right-[10%] h-[400px] w-[500px]"
        style={{ background: 'radial-gradient(ellipse, rgba(37,99,235,0.02), transparent 70%)' }}
        aria-hidden="true"
      />
      {/* Subtle horizontal line */}
      <div
        className="pointer-events-none absolute bottom-0 left-[10%] right-[10%] h-px"
        style={{ background: 'linear-gradient(90deg, transparent, rgba(0,0,0,0.04) 30%, rgba(0,0,0,0.04) 70%, transparent)' }}
        aria-hidden="true"
      />
    </section>
  )
}
