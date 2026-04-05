'use client'

import { motion, useTransform, type MotionValue } from 'framer-motion'
import { FileText, Upload, Search, MessageSquare } from 'lucide-react'
import { ScrollSection } from '../ScrollSection'
import { MeetingWindow, ChatBubble } from '../MeetingWindow'

function Content({ progress }: { progress: MotionValue<number> }) {
  const uploadOpacity = useTransform(progress, [0.05, 0.15], [0, 1])
  const uploadScale = useTransform(progress, [0.05, 0.2], [0.9, 1])

  const scanOpacity = useTransform(progress, [0.2, 0.3], [0, 1])
  const scanLineY = useTransform(progress, [0.2, 0.5], ['0%', '100%'])

  const questionOpacity = useTransform(progress, [0.5, 0.6], [0, 1])
  const questionY = useTransform(progress, [0.5, 0.6], [12, 0])

  const answerOpacity = useTransform(progress, [0.65, 0.8], [0, 1])
  const answerY = useTransform(progress, [0.65, 0.8], [12, 0])

  const highlightOpacity = useTransform(progress, [0.7, 0.85], [0, 1])

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10 w-full">
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-12 items-center">
        <div className="lg:col-span-2">
          <p className="text-sm font-medium text-warm-amber tracking-widest uppercase mb-4">
            Step 03
          </p>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white leading-tight tracking-tight">
            Reads your <br className="hidden md:block" />
            <span className="text-white/40">documents.</span>
          </h2>
          <p className="mt-4 text-base text-white/40 leading-relaxed">
            Upload PDFs, contracts, or slide decks. Cognara references them live during the meeting.
          </p>
        </div>

        <div className="lg:col-span-3">
          <MeetingWindow title="Q2 Planning Standup">
            <div className="space-y-5">
              {/* Upload indicator */}
              <motion.div
                className="flex items-center gap-3 p-3 rounded-xl border border-dashed border-white/10 bg-white/[0.02]"
                style={{ opacity: uploadOpacity, scale: uploadScale }}
              >
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Upload size={18} className="text-blue-400" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-white/70">Q2_Budget_Contract.pdf</p>
                  <p className="text-xs text-white/30">Uploaded — 24 pages indexed</p>
                </div>
                <FileText size={16} className="text-white/20" />
              </motion.div>

              {/* Document scan animation */}
              <motion.div
                className="relative rounded-xl border border-white/[0.06] bg-surface-2/50 p-4 overflow-hidden"
                style={{ opacity: scanOpacity }}
              >
                <div className="space-y-2">
                  <div className="h-2 bg-white/[0.06] rounded w-3/4" />
                  <div className="h-2 bg-white/[0.06] rounded w-full" />
                  <div className="h-2 bg-white/[0.06] rounded w-5/6" />
                  <motion.div
                    className="h-2 rounded w-2/3"
                    style={{
                      backgroundColor: useTransform(highlightOpacity, (v) =>
                        v > 0.5 ? 'rgba(13,148,136,0.25)' : 'rgba(255,255,255,0.06)'
                      ),
                    }}
                  />
                  <div className="h-2 bg-white/[0.06] rounded w-4/5" />
                  <div className="h-2 bg-white/[0.06] rounded w-full" />
                </div>
                {/* Scan line */}
                <motion.div
                  className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-warm-amber/60 to-transparent"
                  style={{ top: scanLineY }}
                />
                <motion.div
                  className="absolute top-2 right-2 flex items-center gap-1"
                  style={{ opacity: scanOpacity }}
                >
                  <Search size={10} className="text-warm-amber/60" />
                  <span className="text-[9px] text-warm-amber/60">Scanning...</span>
                </motion.div>
              </motion.div>

              {/* Question */}
              <motion.div style={{ opacity: questionOpacity, y: questionY }}>
                <ChatBubble
                  name="Alex"
                  color="#3B82F6"
                  message="Cognara, what's our total project budget according to the contract?"
                />
              </motion.div>

              {/* Answer */}
              <motion.div style={{ opacity: answerOpacity, y: answerY }}>
                <div className="p-4 rounded-xl bg-warm-amber/[0.06] border border-warm-amber/10">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare size={14} className="text-warm-amber" />
                    <span className="text-xs font-semibold text-warm-amber">Cognara</span>
                  </div>
                  <p className="text-sm text-white/70">
                    According to <span className="text-warm-amber">Section 4.2</span> of Q2_Budget_Contract.pdf, the total project budget is{' '}
                    <span className="font-semibold text-white">$120,000</span>, allocated across three phases.
                  </p>
                </div>
              </motion.div>
            </div>
          </MeetingWindow>
        </div>
      </div>
    </div>
  )
}

export function DocumentSection() {
  return (
    <ScrollSection height="250vh">
      {(progress) => <Content progress={progress} />}
    </ScrollSection>
  )
}
