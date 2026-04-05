'use client'

import { motion, useTransform, type MotionValue } from 'framer-motion'
import { FileDown, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react'
import { ScrollSection } from '../ScrollSection'

function Content({ progress }: { progress: MotionValue<number> }) {
  const endedOpacity = useTransform(progress, [0.0, 0.1], [0, 1])
  const cardOpacity = useTransform(progress, [0.1, 0.25], [0, 1])
  const cardScale = useTransform(progress, [0.1, 0.25], [0.95, 1])

  const keyPoints = useTransform(progress, [0.25, 0.4], [0, 1])
  const actions = useTransform(progress, [0.4, 0.6], [0, 1])
  const risks = useTransform(progress, [0.6, 0.75], [0, 1])
  const download = useTransform(progress, [0.8, 0.9], [0, 1])

  return (
    <div className="max-w-[1400px] mx-auto px-5 md:px-8 lg:px-12 w-full relative">
      {/* Section ambient */}
      <div
        className="absolute -top-[100px] left-[5%] w-[500px] h-[400px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(175,82,222,0.015), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        <div>
          <p className="text-base font-medium text-warm-amber tracking-widest uppercase mb-4">
            After the meeting
          </p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight">
            Summary <br className="hidden md:block" />
            <span className="text-[#6E6E73]">delivered.</span>
          </h2>
          <p className="mt-5 text-lg text-[#424245] leading-relaxed">
            The moment the meeting ends, Cognara generates a structured summary with action items.
          </p>
        </div>

        <div>
          {/* Meeting ended badge */}
          <motion.div
            className="flex items-center justify-center gap-2 mb-4"
            style={{ opacity: endedOpacity }}
          >
            <div className="w-2 h-2 rounded-full bg-[#AEAEB2]" />
            <span className="text-sm text-[#86868B] font-medium">Meeting ended — 47 min</span>
          </motion.div>

          {/* Summary card */}
          <motion.div
            className="rounded-2xl border border-[#EAE8E4] bg-white overflow-hidden"
            style={{
              opacity: cardOpacity,
              scale: cardScale,
              boxShadow: '0 1px 3px rgba(26, 21, 15, 0.04), 0 8px 32px rgba(26, 21, 15, 0.08)',
            }}
          >
            <div className="px-6 py-4 border-b border-[#EAE8E4] bg-[#FAF9F6] flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[#1D1D1F]">Meeting Summary</h3>
                <p className="text-xs text-[#86868B] mt-0.5">Q2 Planning Standup — Apr 4, 2026</p>
              </div>
              <motion.div className="flex gap-2" style={{ opacity: download }}>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#FAF9F6] border border-[#EAE8E4] text-xs text-[#6E6E73] hover:bg-black/[0.03] transition-colors">
                  <FileDown size={12} /> PDF
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#FAF9F6] border border-[#EAE8E4] text-xs text-[#6E6E73] hover:bg-black/[0.03] transition-colors">
                  <FileDown size={12} /> Word
                </button>
              </motion.div>
            </div>

            <div className="p-6 space-y-6">
              {/* Key Points */}
              <motion.div style={{ opacity: keyPoints }}>
                <h4 className="text-sm font-semibold text-[#6E6E73] uppercase tracking-widest mb-3 flex items-center gap-2">
                  <CheckCircle size={12} className="text-accent-green" />
                  Key Points
                </h4>
                <ul className="space-y-2">
                  {[
                    'Launch postponed to May 14 due to creative review delays',
                    'Engineering on track — 5 of 8 sprints completed',
                    'Budget is $120K across 3 phases per contract Section 4.2',
                  ].map((point, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-accent-green/60 mt-1.5 flex-shrink-0" />
                      <span className="text-base text-[#424245]">{point}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>

              {/* Action Items */}
              <motion.div style={{ opacity: actions }}>
                <h4 className="text-sm font-semibold text-[#6E6E73] uppercase tracking-widest mb-3 flex items-center gap-2">
                  <ArrowRight size={12} className="text-[#007AFF]" />
                  Action Items
                </h4>
                <ul className="space-y-2">
                  {[
                    { owner: 'Sarah', task: 'Finalize campaign assets by May 7' },
                    { owner: 'Alex', task: 'Review analytics dashboard before next standup' },
                    { owner: 'Dev Team', task: 'Complete remaining 3 test suites by May 10' },
                  ].map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-sm font-semibold text-[#007AFF] min-w-[64px]">{item.owner}</span>
                      <span className="text-xs text-[#AEAEB2] mt-0.5">—</span>
                      <span className="text-base text-[#424245]">{item.task}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>

              {/* Risks */}
              <motion.div style={{ opacity: risks }}>
                <h4 className="text-sm font-semibold text-[#6E6E73] uppercase tracking-widest mb-3 flex items-center gap-2">
                  <AlertTriangle size={12} className="text-[#D63031]" />
                  Risks
                </h4>
                <ul className="space-y-2">
                  {[
                    'QA coverage incomplete — 3 test suites still failing',
                    'Agency creative review has no confirmed delivery date',
                  ].map((risk, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-[#D63031]/60 mt-1.5 flex-shrink-0" />
                      <span className="text-base text-[#424245]">{risk}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export function SummarySection() {
  return (
    <ScrollSection height="300vh" className="bg-[#FAF9F6]">
      {(progress) => <Content progress={progress} />}
    </ScrollSection>
  )
}
