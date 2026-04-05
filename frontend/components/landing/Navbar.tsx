'use client'

import { useState, useEffect } from 'react'
import { Menu, X, ArrowRight } from 'lucide-react'
import Link from 'next/link'

const NAV_LINKS = [
  { label: 'Demo', href: '#demo' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Book a Demo', href: '#book-demo' },
]

export function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-[20] transition-all duration-300 ${
        scrolled ? 'glass-nav' : 'bg-transparent'
      }`}
    >
      <nav aria-label="Main navigation" className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10">
        <div className="flex items-center justify-between h-16 md:h-20">
          <a href="#" className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg cta-gradient" aria-hidden="true" />
            <span className="text-lg font-bold text-[#1D1D1F] tracking-tight">Cognara</span>
          </a>

          <div className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-sm text-[#6E6E73] hover:text-[#1D1D1F] transition-colors font-medium"
              >
                {link.label}
              </a>
            ))}
            <Link
              href="/onboarding"
              className="inline-flex items-center h-9 px-4 text-sm font-semibold text-white rounded-full bg-[#2563EB] hover:bg-[#1D4FD7] active:scale-[0.97] transition-all gap-1.5"
            >
              Start free trial
              <ArrowRight size={14} />
            </Link>
          </div>

          <button
            className="md:hidden p-2 text-[#424245]"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {mobileOpen && (
          <div className="md:hidden mt-2 px-4 py-5 space-y-3 rounded-2xl border border-[#EAE8E4] bg-[rgba(250,249,246,0.96)] shadow-lg shadow-[rgba(26,21,15,0.06)] backdrop-blur-2xl">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="block text-base text-[#6E6E73] hover:text-[#1D1D1F] transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <Link
              href="/onboarding"
              className="flex items-center justify-center h-12 text-base font-semibold text-white rounded-full bg-[#2563EB] hover:bg-[#1D4FD7] transition-colors mt-3"
              onClick={() => setMobileOpen(false)}
            >
              Start free trial
            </Link>
          </div>
        )}
      </nav>
    </header>
  )
}
