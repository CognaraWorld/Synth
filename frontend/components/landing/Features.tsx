'use client'

import {
  Mic,
  HandMetal,
  FileText,
  Search,
  Monitor,
  FileDown,
} from 'lucide-react'
import { SectionHeader } from './SectionHeader'
import { ScrollReveal } from './ScrollReveal'

const FEATURES = [
  {
    icon: Mic,
    title: 'Voice Participation',
    description: 'Cognara speaks in meetings with natural voice — not a chatbot, a real participant.',
    color: '#0D9488',
  },
  {
    icon: HandMetal,
    title: 'Wake Word Activation',
    description: 'Always on mute. Call its name and it raises its hand, speaks, then goes back on mute.',
    color: '#00F0FF',
  },
  {
    icon: FileText,
    title: 'Document Comprehension',
    description: 'Upload PDFs, Word docs, or slide decks. Cognara reads and references them live.',
    color: '#8000FF',
  },
  {
    icon: Search,
    title: 'Live Web Search',
    description: 'Need a fact-check mid-meeting? Cognara searches the web and responds in seconds.',
    color: '#00E676',
  },
  {
    icon: Monitor,
    title: 'Screen Share OCR',
    description: 'Watches shared screens, reads text from slides and dashboards in real time.',
    color: '#0F766E',
  },
  {
    icon: FileDown,
    title: 'Meeting Summary',
    description: 'After every meeting, get a comprehensive summary with action items as PDF or Word.',
    color: '#2D8CFF',
  },
]

export function Features() {
  return (
    <section id="features" aria-labelledby="features-heading" className="py-16 md:py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10">
        <SectionHeader
          number="01"
          heading="Everything your meetings need"
          subtitle="Cognara doesn't just listen — it participates, researches, and delivers results."
        />

        <ScrollReveal stagger={0.1} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((feature) => {
            const Icon = feature.icon
            return (
              <div
                key={feature.title}
                className="glass-card rounded-2xl p-6 md:p-8 group hover:border-white/20 transition-all duration-300"
              >
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                  style={{ backgroundColor: `${feature.color}15` }}
                >
                  <Icon size={24} style={{ color: feature.color }} />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-sm text-text-muted leading-relaxed">{feature.description}</p>
              </div>
            )
          })}
        </ScrollReveal>
      </div>
    </section>
  )
}
