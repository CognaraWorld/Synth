'use client'

import { Check, ArrowRight } from 'lucide-react'
import { SectionHeader } from './SectionHeader'
import { ScrollReveal } from './ScrollReveal'

const FEATURES = [
  'Unlimited meetings',
  'Zoom, Teams & Google Meet',
  'Voice participation',
  'Document comprehension',
  'Web search in meetings',
  'Meeting summaries (PDF & Word)',
  'Custom bot persona',
  'Screen share OCR',
]

export function Pricing() {
  return (
    <section id="pricing" aria-labelledby="pricing-heading" className="py-16 md:py-24 lg:py-32 bg-surface-1">
      <div className="max-w-3xl mx-auto px-4 md:px-8 lg:px-10">
        <SectionHeader
          number="04"
          heading="Simple, transparent pricing"
          subtitle="One plan. Everything included. No hidden fees."
        />

        <ScrollReveal>
          <div className="glass-card rounded-2xl p-8 md:p-12 border border-warm-amber/20 section-glow">
            <div className="text-center">
              <span className="inline-block px-3 py-1 text-xs font-semibold text-warm-amber bg-warm-amber/10 rounded-full uppercase tracking-wide mb-4">
                Pro Plan
              </span>

              <div className="flex items-baseline justify-center gap-1 mb-2">
                <span className="text-5xl md:text-6xl font-bold text-white">&#8377;5,000</span>
                <span className="text-text-muted text-lg">/month</span>
              </div>

              <p className="text-sm text-text-muted mb-8">Everything you need to supercharge your meetings</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left mb-10 max-w-md mx-auto">
                {FEATURES.map((feature) => (
                  <div key={feature} className="flex items-center gap-2.5">
                    <div className="w-5 h-5 rounded-full bg-accent-green/10 flex items-center justify-center flex-shrink-0">
                      <Check size={12} className="text-accent-green" />
                    </div>
                    <span className="text-sm text-white/80">{feature}</span>
                  </div>
                ))}
              </div>

              <a
                href="/onboarding"
                className="inline-flex items-center justify-center h-14 px-10 text-base font-semibold text-white rounded-full cta-gradient transition-all duration-200 hover:shadow-lg hover:shadow-warm-amber/25 active:scale-[0.97] gap-2"
              >
                Start Free Trial
                <ArrowRight size={18} />
              </a>

              <p className="mt-4 text-xs text-text-muted">No credit card required. 14-day free trial.</p>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
