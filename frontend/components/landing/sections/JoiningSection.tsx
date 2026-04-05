'use client'

import { motion, useTransform, type MotionValue } from 'framer-motion'
import { ScrollSection } from '../ScrollSection'
import { MeetingWindow, Participant, ChatBubble } from '../MeetingWindow'
import { Waveform } from '../Waveform'

function Content({ progress }: { progress: MotionValue<number> }) {
  // Animation phases
  const joiningOpacity = useTransform(progress, [0, 0.1], [0, 1])
  const joiningScale = useTransform(progress, [0, 0.15], [0.92, 1])

  const cognaraOpacity = useTransform(progress, [0.1, 0.25], [0, 1])
  const cognaraY = useTransform(progress, [0.1, 0.25], [20, 0])

  const statusOpacity = useTransform(progress, [0.25, 0.35], [0, 1])
  const waveformOpacity = useTransform(progress, [0.35, 0.45], [0, 1])

  const msg1Opacity = useTransform(progress, [0.5, 0.6], [0, 1])
  const msg1Y = useTransform(progress, [0.5, 0.6], [12, 0])

  const msg2Opacity = useTransform(progress, [0.7, 0.8], [0, 1])
  const msg2Y = useTransform(progress, [0.7, 0.8], [12, 0])

  return (
    <div className="max-w-[1400px] mx-auto px-5 md:px-8 lg:px-12 w-full relative">
      {/* Section ambient */}
      <div
        className="absolute -top-[200px] -left-[200px] w-[600px] h-[500px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(37,99,235,0.02), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        {/* Left text */}
        <div>
          <motion.p
            className="text-base font-medium text-warm-amber tracking-widest uppercase mb-4"
            style={{ opacity: joiningOpacity }}
          >
            Step 01
          </motion.p>
          <motion.h2
            className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight"
            style={{ opacity: joiningOpacity }}
          >
            Cognara joins <br className="hidden md:block" />
            <span className="text-[#6E6E73]">the meeting.</span>
          </motion.h2>
          <motion.p
            className="mt-5 text-lg text-[#424245] leading-relaxed"
            style={{ opacity: statusOpacity }}
          >
            Paste a meeting link. Cognara joins as a participant — you don&apos;t even need to be there.
          </motion.p>
        </div>

        {/* Right meeting UI */}
        <motion.div
          className=""
          style={{ opacity: joiningOpacity, scale: joiningScale }}
        >
          <MeetingWindow title="Q2 Planning Standup" status="Cognara is listening...">
            <div className="flex items-center justify-center gap-6 md:gap-8 mb-6">
              <Participant name="Alex" initials="AK" color="#3B82F6" speaking />
              <Participant name="Sarah" initials="SL" color="#8B5CF6" />
              <motion.div style={{ opacity: cognaraOpacity, y: cognaraY }}>
                <Participant name="Cognara" initials="C" color="#0D9488" ai status="Joined" />
              </motion.div>
            </div>

            <motion.div className="flex justify-center mb-5" style={{ opacity: waveformOpacity }}>
              <motion.div>
                <WaveformWrapper progress={progress} />
              </motion.div>
            </motion.div>

            <div className="border-t border-[#EAE8E4] pt-4 space-y-4">
              <p className="text-xs text-[#86868B] font-medium uppercase tracking-widest">
                Transcript
              </p>
              <motion.div style={{ opacity: msg1Opacity, y: msg1Y }}>
                <ChatBubble
                  name="Alex"
                  color="#3B82F6"
                  message="What's the status of the launch? Are we still on track for May?"
                />
              </motion.div>
              <motion.div style={{ opacity: msg2Opacity, y: msg2Y }}>
                <ChatBubble
                  name="Sarah"
                  color="#8B5CF6"
                  message="Marketing assets are delayed. We're waiting on creative review from the agency."
                />
              </motion.div>
            </div>
          </MeetingWindow>
        </motion.div>
      </div>
    </div>
  )
}

function WaveformWrapper({ progress }: { progress: MotionValue<number> }) {
  void progress
  return <Waveform active bars={32} />
}

export function JoiningSection() {
  return (
    <ScrollSection height="250vh" id="demo" className="bg-[#FAF9F6]">
      {(progress) => <Content progress={progress} />}
    </ScrollSection>
  )
}
