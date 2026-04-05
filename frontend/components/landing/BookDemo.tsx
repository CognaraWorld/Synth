'use client'

import { useState } from 'react'
import { Send } from 'lucide-react'
import { SectionHeader } from './SectionHeader'
import { ScrollReveal } from './ScrollReveal'

export function BookDemo() {
  const [submitted, setSubmitted] = useState(false)

  return (
    <section id="book-demo" aria-labelledby="book-demo-heading" className="py-16 md:py-24 lg:py-32">
      <div className="max-w-3xl mx-auto px-4 md:px-8 lg:px-10">
        <SectionHeader
          number="05"
          heading="Book a demo"
          subtitle="See Cognara tailored to your workflow. We'll walk you through everything."
        />

        <ScrollReveal>
          <div className="glass-card rounded-2xl p-6 md:p-10">
            {submitted ? (
              <div className="text-center py-8" role="status" aria-live="polite">
                <div className="w-16 h-16 rounded-full bg-accent-green/10 flex items-center justify-center mx-auto mb-4">
                  <Send size={28} className="text-accent-green" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">We&apos;ll be in touch!</h3>
                <p className="text-text-muted">Thanks for your interest. We&apos;ll reach out within 24 hours.</p>
              </div>
            ) : (
              <form
                onSubmit={(e) => { e.preventDefault(); setSubmitted(true) }}
                className="grid grid-cols-1 sm:grid-cols-2 gap-5"
              >
                <div className="flex flex-col gap-2">
                  <label htmlFor="demo-name" className="text-sm font-medium text-white/80">
                    Name <span className="text-warm-amber" aria-hidden="true">*</span>
                  </label>
                  <input
                    type="text"
                    id="demo-name"
                    name="name"
                    required
                    aria-required="true"
                    autoComplete="name"
                    className="h-11 px-4 rounded-lg bg-surface-2 border border-white/10 text-white text-sm placeholder:text-text-muted focus:outline-2 focus:outline-offset-2 focus:outline-warm-amber focus:border-warm-amber transition-colors"
                    placeholder="Your name"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <label htmlFor="demo-email" className="text-sm font-medium text-white/80">
                    Email <span className="text-warm-amber" aria-hidden="true">*</span>
                  </label>
                  <input
                    type="email"
                    id="demo-email"
                    name="email"
                    required
                    aria-required="true"
                    autoComplete="email"
                    className="h-11 px-4 rounded-lg bg-surface-2 border border-white/10 text-white text-sm placeholder:text-text-muted focus:outline-2 focus:outline-offset-2 focus:outline-warm-amber focus:border-warm-amber transition-colors"
                    placeholder="you@example.com"
                  />
                </div>

                <div className="flex flex-col gap-2 sm:col-span-2">
                  <label htmlFor="demo-company" className="text-sm font-medium text-white/80">
                    Company
                  </label>
                  <input
                    type="text"
                    id="demo-company"
                    name="company"
                    autoComplete="organization"
                    className="h-11 px-4 rounded-lg bg-surface-2 border border-white/10 text-white text-sm placeholder:text-text-muted focus:outline-2 focus:outline-offset-2 focus:outline-warm-amber focus:border-warm-amber transition-colors"
                    placeholder="Company name (optional)"
                  />
                </div>

                <div className="flex flex-col gap-2 sm:col-span-2">
                  <label htmlFor="demo-message" className="text-sm font-medium text-white/80">
                    Message
                  </label>
                  <textarea
                    id="demo-message"
                    name="message"
                    rows={4}
                    className="px-4 py-3 rounded-lg bg-surface-2 border border-white/10 text-white text-sm placeholder:text-text-muted focus:outline-2 focus:outline-offset-2 focus:outline-warm-amber focus:border-warm-amber transition-colors resize-none"
                    placeholder="Tell us about your use case..."
                  />
                </div>

                <div className="sm:col-span-2 flex justify-center pt-2">
                  <button
                    type="submit"
                    className="inline-flex items-center justify-center h-12 px-8 text-base font-semibold text-white rounded-full cta-gradient transition-all duration-200 hover:shadow-lg hover:shadow-warm-amber/25 active:scale-[0.97] gap-2"
                  >
                    <Send size={16} />
                    Send Request
                  </button>
                </div>
              </form>
            )}
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
