'use client'

import { motion, useTransform, type MotionValue } from 'framer-motion'
import { Hand } from 'lucide-react'
import { ScrollSection } from '../ScrollSection'
import { MeetingWindow, Participant, ChatBubble } from '../MeetingWindow'
import { Waveform } from '../Waveform'

function Content({ progress }: { progress: MotionValue<number> }) {
  const questionOpacity = useTransform(progress, [0.05, 0.15], [0, 1])
  const questionY = useTransform(progress, [0.05, 0.15], [12, 0])

  const handOpacity = useTransform(progress, [0.2, 0.3], [0, 1])
  const handScale = useTransform(progress, [0.2, 0.35], [0.5, 1])
  const handGlow = useTransform(progress, [0.2, 0.4], [0, 1])

  const speakingOpacity = useTransform(progress, [0.4, 0.5], [0, 1])
  const waveformOpacity = useTransform(progress, [0.45, 0.55], [0, 1])

  const bullet1 = useTransform(progress, [0.55, 0.65], [0, 1])
  const bullet2 = useTransform(progress, [0.65, 0.75], [0, 1])
  const bullet3 = useTransform(progress, [0.75, 0.85], [0, 1])

  const bullets = [
    { text: 'Marketing delay — creative review pending from agency', opacity: bullet1 },
    { text: 'QA sprint incomplete — 3 of 8 test suites failing', opacity: bullet2 },
    { text: 'Launch may slip 1 week to May 14th based on current velocity', opacity: bullet3 },
  ]

  return (
    <div className="max-w-[1400px] mx-auto px-5 md:px-8 lg:px-12 w-full relative">
      {/* Section ambient */}
      <div
        className="absolute -top-[100px] -right-[200px] w-[500px] h-[500px] opacity-[0.05] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(13,148,136,0.03), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        <div>
          <p className="text-base font-medium text-warm-amber tracking-widest uppercase mb-4">
            Step 02
          </p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight">
            Ask Cognara <br className="hidden md:block" />
            <span className="text-[#6E6E73]">anything.</span>
          </h2>
          <p className="mt-5 text-lg text-[#424245] leading-relaxed">
            Call its name in the meeting. Cognara raises its hand, waits for its turn, and speaks.
          </p>
        </div>

        <div>
          <MeetingWindow title="Q2 Planning Standup">
            <div className="flex items-center justify-center gap-6 md:gap-8 mb-6">
              <Participant name="Alex" initials="AK" color="#3B82F6" />
              <Participant name="Sarah" initials="SL" color="#8B5CF6" />
              <Participant name="Cognara" initials="C" color="#0D9488" ai speaking />
            </div>

            <div className="space-y-4">
              {/* Alex asks */}
              <motion.div style={{ opacity: questionOpacity, y: questionY }}>
                <ChatBubble
                  name="Alex"
                  color="#3B82F6"
                  message="Hey Cognara, can you summarize the key risks for this launch?"
                />
              </motion.div>

              {/* Hand raise */}
              <motion.div
                className="flex items-center justify-center gap-2 py-3"
                style={{ opacity: handOpacity }}
              >
                <motion.div
                  style={{
                    scale: handScale,
                    filter: useTransform(handGlow, (v) => `drop-shadow(0 0 ${v * 12}px rgba(13, 148, 136, 0.35))`),
                  }}
                >
                  <Hand size={20} className="text-warm-amber" />
                </motion.div>
                <span className="text-sm text-warm-amber font-medium">Cognara raised hand</span>
              </motion.div>

              {/* Speaking indicator */}
              <motion.div className="flex justify-center" style={{ opacity: waveformOpacity }}>
                <Waveform active bars={28} />
              </motion.div>

              {/* Response */}
              <motion.div style={{ opacity: speakingOpacity }}>
                <div className="mt-2 p-4 rounded-xl bg-[#F0FDFA] border border-[#0D9488]/15">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-5 h-5 rounded-full bg-[#0D9488]/12 flex items-center justify-center">
                      <span className="text-[9px] font-bold text-warm-amber">C</span>
                    </div>
                    <span className="text-sm font-semibold text-warm-amber">Cognara</span>
                  </div>
                  <p className="text-base text-[#424245] mb-3">
                    Based on the discussion, here are the key risks:
                  </p>
                  <div className="space-y-2">
                    {bullets.map((bullet, i) => (
                      <motion.div
                        key={i}
                        className="flex items-start gap-2"
                        style={{ opacity: bullet.opacity }}
                      >
                        <div className="w-1.5 h-1.5 rounded-full bg-warm-amber mt-2 flex-shrink-0" />
                        <span className="text-base text-[#424245]">{bullet.text}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.div>
            </div>
          </MeetingWindow>
        </div>
      </div>
    </div>
  )
}

export function AskingSection() {
  return (
    <ScrollSection height="300vh" className="bg-white">
      {(progress) => <Content progress={progress} />}
    </ScrollSection>
  )
}
