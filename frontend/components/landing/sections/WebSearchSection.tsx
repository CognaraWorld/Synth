'use client'

import { motion, useTransform, type MotionValue } from 'framer-motion'
import { Globe, ExternalLink, CheckCircle } from 'lucide-react'
import { ScrollSection } from '../ScrollSection'
import { MeetingWindow, ChatBubble } from '../MeetingWindow'

const SEARCH_RESULTS = [
  { title: 'OpenAI valued at $300B in latest funding round', source: 'reuters.com' },
  { title: 'OpenAI closes record $40B raise led by SoftBank', source: 'techcrunch.com' },
  { title: 'AI startup valuations surge in 2025', source: 'bloomberg.com' },
]

function Content({ progress }: { progress: MotionValue<number> }) {
  const questionOpacity = useTransform(progress, [0.05, 0.15], [0, 1])
  const questionY = useTransform(progress, [0.05, 0.15], [12, 0])

  const searchingOpacity = useTransform(progress, [0.2, 0.3], [0, 1])
  const spinnerRotate = useTransform(progress, [0.2, 0.5], [0, 720])

  const result1 = useTransform(progress, [0.35, 0.42], [0, 1])
  const result2 = useTransform(progress, [0.42, 0.49], [0, 1])
  const result3 = useTransform(progress, [0.49, 0.56], [0, 1])
  const resultOpacities = [result1, result2, result3]

  const answerOpacity = useTransform(progress, [0.65, 0.8], [0, 1])
  const answerY = useTransform(progress, [0.65, 0.8], [12, 0])

  const verifiedOpacity = useTransform(progress, [0.85, 0.95], [0, 1])

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10 w-full">
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-12 items-center">
        <div className="lg:col-span-2">
          <p className="text-sm font-medium text-warm-amber tracking-widest uppercase mb-4">
            Step 04
          </p>
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white leading-tight tracking-tight">
            Searches the web <br className="hidden md:block" />
            <span className="text-white/40">in real time.</span>
          </h2>
          <p className="mt-4 text-base text-white/40 leading-relaxed">
            Need a fact-check mid-meeting? Cognara searches, verifies, and responds in seconds.
          </p>
        </div>

        <div className="lg:col-span-3">
          <MeetingWindow title="Q2 Planning Standup">
            <div className="space-y-4">
              {/* Question */}
              <motion.div style={{ opacity: questionOpacity, y: questionY }}>
                <ChatBubble
                  name="Sarah"
                  color="#8B5CF6"
                  message="Cognara, what's the latest OpenAI valuation? We need it for the competitive analysis."
                />
              </motion.div>

              {/* Searching indicator */}
              <motion.div
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]"
                style={{ opacity: searchingOpacity }}
              >
                <motion.div style={{ rotate: spinnerRotate }}>
                  <Globe size={14} className="text-warm-amber" />
                </motion.div>
                <span className="text-xs text-white/40">Searching the web...</span>
              </motion.div>

              {/* Results */}
              <div className="space-y-2">
                {SEARCH_RESULTS.map((result, i) => (
                  <motion.div
                    key={i}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                    style={{ opacity: resultOpacities[i] }}
                  >
                    <ExternalLink size={12} className="text-white/20 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-white/50 truncate">{result.title}</p>
                      <p className="text-[10px] text-white/20">{result.source}</p>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Answer */}
              <motion.div style={{ opacity: answerOpacity, y: answerY }}>
                <div className="p-4 rounded-xl bg-warm-amber/[0.06] border border-warm-amber/10">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-warm-amber">Cognara</span>
                  </div>
                  <p className="text-sm text-white/70">
                    OpenAI&apos;s latest valuation is <span className="font-semibold text-white">$300 billion</span>,
                    following a $40B funding round led by SoftBank, closed in March 2025.
                  </p>
                  <motion.div
                    className="flex items-center gap-1.5 mt-3"
                    style={{ opacity: verifiedOpacity }}
                  >
                    <CheckCircle size={12} className="text-accent-green" />
                    <span className="text-[10px] text-accent-green/80 font-medium">
                      Verified via live web search — 3 sources
                    </span>
                  </motion.div>
                </div>
              </motion.div>
            </div>
          </MeetingWindow>
        </div>
      </div>
    </div>
  )
}

export function WebSearchSection() {
  return (
    <ScrollSection height="250vh">
      {(progress) => <Content progress={progress} />}
    </ScrollSection>
  )
}
