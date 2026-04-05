'use client'

import { motion } from 'framer-motion'
import { Check, ArrowRight } from 'lucide-react'
import Link from 'next/link'

const PLANS = [
  {
    name: 'Free',
    price: '0',
    period: 'forever',
    description: 'Try Cognara risk-free',
    features: ['5 meetings included', 'Voice participation', 'Meeting summaries', 'Basic web search'],
    cta: 'Get started',
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '5,000',
    period: '/month',
    description: 'For professionals and teams',
    features: [
      'Unlimited meetings',
      'Zoom, Teams & Google Meet',
      'Document comprehension',
      'Advanced web search',
      'Custom bot persona',
      'Screen share OCR',
      'PDF & Word exports',
      'Priority support',
    ],
    cta: 'Start free trial',
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'Self-hosted deployment',
    features: ['Everything in Pro', 'On-premise deployment', 'Custom integrations', 'Dedicated support', 'SLA guarantee'],
    cta: 'Contact sales',
    highlighted: false,
  },
]

export function PricingSection() {
  return (
    <section id="pricing" className="py-20 md:py-28 lg:py-36 px-4 md:px-8 lg:px-12 relative overflow-hidden bg-[#FAF9F6]">
      {/* Section ambient */}
      <div
        className="absolute top-[15%] left-1/2 -translate-x-1/2 w-[700px] h-[500px] opacity-[0.04] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(13,148,136,0.03), transparent 60%)', filter: 'blur(100px)' }}
        aria-hidden="true"
      />
      <div className="max-w-6xl mx-auto relative z-[1]">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7 }}
        >
          <p className="text-base font-medium text-warm-amber tracking-widest uppercase mb-4">
            Pricing
          </p>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-[#1D1D1F] leading-tight tracking-tight">
            Simple, transparent pricing.
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PLANS.map((plan, i) => (
            <motion.div
              key={plan.name}
              className={`rounded-2xl p-7 md:p-10 flex flex-col ${
                plan.highlighted
                  ? 'border border-[#2563EB]/20 bg-white'
                  : 'border border-[#EAE8E4] bg-white'
              }`}
              style={{
                boxShadow: plan.highlighted
                  ? '0 1px 3px rgba(26, 21, 15, 0.04), 0 16px 48px rgba(37, 99, 235, 0.10)'
                  : '0 1px 3px rgba(26, 21, 15, 0.04)',
              }}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.6, delay: i * 0.1 }}
            >
              {plan.highlighted && (
                <span className="inline-block self-start px-2.5 py-1 text-[10px] font-semibold text-white bg-[#2563EB] rounded-full uppercase tracking-wide mb-4">
                  Most Popular
                </span>
              )}

              <h3 className="text-xl font-semibold text-[#1D1D1F]">{plan.name}</h3>
              <p className="text-sm text-[#86868B] mt-1">{plan.description}</p>

              <div className="flex items-baseline gap-1 mt-4 mb-6">
                {plan.price !== 'Custom' && <span className="text-xs text-[#86868B]">&#8377;</span>}
                <span className="text-5xl font-bold text-[#1D1D1F]">{plan.price}</span>
                {plan.period && <span className="text-base text-[#86868B]">{plan.period}</span>}
              </div>

              <ul className="space-y-3.5 flex-1">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2.5">
                    <div
                      className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                        plan.highlighted ? 'bg-[#EFF6FF]' : 'bg-black/[0.03]'
                      }`}
                    >
                      <Check size={10} className={plan.highlighted ? 'text-[#2563EB]' : 'text-[#86868B]'} />
                    </div>
                    <span className="text-base text-[#424245]">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={plan.name === 'Enterprise' ? '#book-demo' : '/onboarding'}
                className={`mt-8 inline-flex items-center justify-center h-13 px-8 text-base font-semibold rounded-full transition-all gap-2 ${
                  plan.highlighted
                    ? 'bg-[#2563EB] text-white hover:bg-[#1D4FD7] active:scale-[0.97]'
                    : 'border border-[#EAE8E4] text-[#424245] hover:bg-black/[0.03]'
                }`}
              >
                {plan.cta}
                {plan.highlighted && <ArrowRight size={14} />}
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
