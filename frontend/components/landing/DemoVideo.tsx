'use client'

import { Play } from 'lucide-react'
import { SectionHeader } from './SectionHeader'
import { ScrollReveal } from './ScrollReveal'

export function DemoVideo() {
  return (
    <section id="demo" aria-labelledby="demo-heading" className="py-16 md:py-24 lg:py-32">
      <div className="max-w-5xl mx-auto px-4 md:px-8 lg:px-10">
        <SectionHeader
          number="03"
          heading="See Cognara in action"
          subtitle="Watch how Cognara joins a meeting, listens, and participates in real time."
        />

        <ScrollReveal>
          <div className="relative aspect-video rounded-2xl overflow-hidden border border-white/10 bg-surface-2 group">
            {/* Video placeholder */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <button
                className="w-20 h-20 rounded-full cta-gradient flex items-center justify-center shadow-lg shadow-warm-amber/20 group-hover:scale-105 transition-transform duration-300"
                aria-label="Play demo video"
              >
                <Play size={32} className="text-white ml-1" />
              </button>
              <p className="text-sm text-text-muted">Demo video coming soon</p>
            </div>

            {/* Ambient glow */}
            <div
              className="absolute inset-0 pointer-events-none opacity-20"
              style={{
                background: 'radial-gradient(ellipse at center, #0D9488, transparent 70%)',
              }}
              aria-hidden="true"
            />
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
