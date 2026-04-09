'use client'

import { motion, useTransform, type MotionValue } from 'framer-motion'
import { Mic, Brain, Globe, Cpu, AudioLines, MessageSquare } from 'lucide-react'
import { ScrollSection } from '../ScrollSection'

const PIPELINE_NODES = [
  { icon: Mic, label: 'Meeting Audio', sub: 'Live capture' },
  { icon: AudioLines, label: 'Speech Recognition', sub: 'Whisper' },
  { icon: Brain, label: 'Context Engine', sub: 'Memory + documents' },
  { icon: Globe, label: 'Web Search', sub: 'SearXNG' },
  { icon: Cpu, label: 'Reasoning', sub: 'Claude' },
  { icon: MessageSquare, label: 'Voice Response', sub: 'Kokoro TTS' },
]

function PipelineNode({
  node,
  index,
  progress,
  isLast,
}: {
  node: (typeof PIPELINE_NODES)[number]
  index: number
  progress: MotionValue<number>
  isLast: boolean
}) {
  const start = 0.1 + index * 0.13
  const end = start + 0.1
  const nodeOpacity = useTransform(progress, [start, end], [0.2, 1])
  const nodeScale = useTransform(progress, [start, end], [0.95, 1])
  const glowIntensity = useTransform(progress, [start, end], [0, 1])
  const boxShadow = useTransform(
    glowIntensity,
    (v) => `0 0 ${v * 30}px rgba(13, 148, 136, ${v * 0.12})`
  )
  const borderColor = useTransform(
    glowIntensity,
    (v) => (v === 0 ? '#EAE8E4' : `rgba(13, 148, 136, ${0.08 + v * 0.17})`)
  )
  const bgColor = useTransform(
    glowIntensity,
    (v) => `rgba(13, 148, 136, ${0.06 + v * 0.09})`
  )
  const connectorBg = useTransform(progress, [start + 0.06, end + 0.06], [
    '#EAE8E4',
    'rgba(13,148,136,0.5)',
  ])
  const Icon = node.icon

  return (
    <div className="flex flex-col items-center">
      <motion.div
        className="relative flex items-center gap-4 px-6 py-4 rounded-2xl border border-[#EAE8E4] bg-white shadow-[0_1px_3px_rgba(26,21,15,0.04)]"
        style={{ opacity: nodeOpacity, scale: nodeScale, boxShadow, borderColor }}
      >
        <motion.div
          className="w-12 h-12 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: bgColor }}
        >
          <Icon
            size={24}
            className="text-warm-amber"
            style={{ filter: 'drop-shadow(0 0 4px rgba(13,148,136,0.22))' }}
          />
        </motion.div>
        <div>
          <p className="text-base font-semibold text-[#1D1D1F]">{node.label}</p>
          <p className="text-sm text-[#6E6E73]">{node.sub}</p>
        </div>
      </motion.div>

      {!isLast && (
        <motion.div
          className="w-px h-6 md:h-8"
          style={{ background: connectorBg }}
        />
      )}
    </div>
  )
}

function Content({ progress }: { progress: MotionValue<number> }) {
  const titleOpacity = useTransform(progress, [0, 0.1], [0, 1])

  return (
    <div className="max-w-[1400px] mx-auto px-5 md:px-8 lg:px-12 w-full relative">
      {/* Section ambient */}
      <div
        className="absolute top-[10%] left-[10%] w-[400px] h-[400px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(37,99,235,0.02), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div
        className="absolute bottom-[10%] right-[10%] w-[400px] h-[400px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(13,148,136,0.03), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
        {/* Left text */}
        <motion.div style={{ opacity: titleOpacity }}>
          <p className="text-base font-medium text-warm-amber tracking-widest uppercase mb-4">
            Under the hood
          </p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight">
            Six systems.
            <br />
            <span className="text-[#6E6E73]">One voice.</span>
          </h2>
          <p className="mt-5 text-lg text-[#424245] leading-relaxed max-w-lg">
            Every response flows through a real-time pipeline — from audio capture to spoken answer in under 3 seconds.
          </p>
        </motion.div>

        {/* Right pipeline */}
        <div className="flex flex-col items-center gap-0">
          {PIPELINE_NODES.map((node, i) => (
            <PipelineNode
              key={i}
              node={node}
              index={i}
              progress={progress}
              isLast={i === PIPELINE_NODES.length - 1}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

export function ThinkingSection() {
  return (
    <ScrollSection height="250vh" className="bg-[#FAF9F6]">
      {(progress) => <Content progress={progress} />}
    </ScrollSection>
  )
}
