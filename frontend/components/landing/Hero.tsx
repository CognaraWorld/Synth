'use client'

import { useRef } from 'react'
import dynamic from 'next/dynamic'
import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { ArrowRight, Play } from 'lucide-react'

const HeroCanvas = dynamic(() => import('./HeroCanvas').then(mod => ({ default: mod.HeroCanvas })), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center">
      <div className="w-48 h-48 rounded-full bg-gradient-to-br from-warm-amber/20 to-ai-purple/20 blur-3xl" />
    </div>
  ),
})

export function Hero() {
  const heroRef = useRef<HTMLElement>(null)

  useGSAP(() => {
    const prefersReducedMotion = window.matchMedia(
      '(prefers-reduced-motion: reduce)'
    ).matches

    if (prefersReducedMotion) return

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })

    tl.from('[data-hero-badge]', { y: 20, opacity: 0, duration: 0.5 }, 0.2)
      .from('[data-hero-heading] .hero-word', { y: 60, opacity: 0, duration: 0.7, stagger: 0.08 }, 0.3)
      .from('[data-hero-sub]', { y: 20, opacity: 0, duration: 0.5 }, 0.8)
      .from('[data-hero-ctas]', { y: 20, opacity: 0, duration: 0.5 }, 1.0)
      .from('[data-hero-canvas]', { opacity: 0, scale: 0.9, duration: 1.0 }, 0.5)
  }, { scope: heroRef })

  const headingWords = 'Your AI teammate for every meeting'.split(' ')

  return (
    <section
      ref={heroRef}
      aria-labelledby="hero-heading"
      className="relative min-h-screen flex items-center pt-20 md:pt-0 overflow-hidden"
    >
      <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-16 items-center">
          {/* Left — text */}
          <div className="z-10 order-2 lg:order-1">
            <div data-hero-badge className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-warm-amber/30 bg-warm-amber/5 mb-6">
              <span className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
              <span className="text-xs font-medium text-warm-amber tracking-wide uppercase">Now in Beta</span>
            </div>

            <h1
              id="hero-heading"
              data-hero-heading
              className="text-4xl md:text-5xl lg:text-6xl xl:text-7xl font-bold text-white leading-[1.05] tracking-tight"
            >
              {headingWords.map((word, i) => (
                <span key={i} className="hero-word inline-block mr-[0.25em]">
                  {word === 'AI' ? <span className="gradient-text">{word}</span> : word}
                </span>
              ))}
            </h1>

            <p data-hero-sub className="mt-6 text-lg md:text-xl text-text-muted leading-relaxed max-w-lg">
              An AI-powered meeting bot that joins Zoom, Microsoft Teams, and Google Meet as an active voice participant.
            </p>

            <div data-hero-ctas className="mt-8 flex flex-wrap items-center gap-4">
              <a
                href="/onboarding"
                className="inline-flex items-center justify-center h-12 md:h-14 px-6 md:px-8 text-base font-semibold text-white rounded-full cta-gradient transition-all duration-200 hover:shadow-lg hover:shadow-warm-amber/25 active:scale-[0.97] gap-2"
              >
                Start Free Trial
                <ArrowRight size={18} />
              </a>
              <a
                href="#demo"
                className="inline-flex items-center justify-center h-12 md:h-14 px-6 md:px-8 text-base font-medium text-white rounded-full border border-white/15 hover:border-white/30 hover:bg-white/5 transition-all duration-200 gap-2"
              >
                <Play size={16} className="text-warm-amber" />
                Watch Demo
              </a>
            </div>
          </div>

          {/* Right — 3D canvas */}
          <div
            data-hero-canvas
            className="relative order-1 lg:order-2 h-[340px] md:h-[480px] lg:h-[580px]"
          >
            <HeroCanvas />
            {/* Ambient glow behind the orb */}
            <div
              className="absolute inset-0 -z-10 blur-3xl opacity-30"
              style={{
                background: 'radial-gradient(circle at 50% 50%, #0D9488, transparent 60%)',
              }}
              aria-hidden="true"
            />
          </div>
        </div>
      </div>

      {/* Bottom gradient fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-bg-dark to-transparent pointer-events-none"
        aria-hidden="true"
      />
    </section>
  )
}
