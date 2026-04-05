'use client'

import { UserPlus, Link2, Bot } from 'lucide-react'
import { SectionHeader } from './SectionHeader'
import { ScrollReveal } from './ScrollReveal'

const STEPS = [
  {
    icon: UserPlus,
    step: '1',
    title: 'Create Your Agent',
    description: 'Describe the persona you want — a helpful assistant, a domain expert, or a custom role. Cognara tailors itself to your needs.',
  },
  {
    icon: Link2,
    step: '2',
    title: 'Paste Your Meeting Link',
    description: 'Drop in your Zoom, Teams, or Google Meet link. Upload any documents you want the bot to reference during the meeting.',
  },
  {
    icon: Bot,
    step: '3',
    title: 'Bot Joins & Participates',
    description: 'Cognara joins independently — you don\'t even need to be there. It listens, speaks when called, and delivers a summary after.',
  },
]

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      aria-labelledby="how-it-works-heading"
      className="py-16 md:py-24 lg:py-32 bg-surface-1"
    >
      <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10">
        <SectionHeader
          number="02"
          heading="Three steps. That's it."
          subtitle="From setup to meeting in under a minute."
        />

        <ScrollReveal stagger={0.15} className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {STEPS.map((step, i) => {
            const Icon = step.icon
            return (
              <div key={step.step} className="relative text-center md:text-left">
                {/* Connector line (desktop only) */}
                {i < STEPS.length - 1 && (
                  <div
                    className="hidden md:block absolute top-8 left-[calc(50%+40px)] right-[calc(-50%+40px)] h-px bg-gradient-to-r from-warm-amber/30 to-transparent"
                    aria-hidden="true"
                  />
                )}

                <div className="flex flex-col items-center md:items-start">
                  <div className="relative mb-6">
                    <div className="w-16 h-16 rounded-2xl bg-warm-amber/10 flex items-center justify-center">
                      <Icon size={28} className="text-warm-amber" />
                    </div>
                    <span className="absolute -top-2 -right-2 w-7 h-7 rounded-full cta-gradient flex items-center justify-center text-xs font-bold text-white">
                      {step.step}
                    </span>
                  </div>

                  <h3 className="text-xl font-semibold text-white mb-3">{step.title}</h3>
                  <p className="text-sm text-text-muted leading-relaxed max-w-xs">{step.description}</p>
                </div>
              </div>
            )
          })}
        </ScrollReveal>
      </div>
    </section>
  )
}
