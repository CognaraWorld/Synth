'use client'

import { ScrollReveal } from './ScrollReveal'

const PLATFORMS = [
  { name: 'Zoom', color: '#2D8CFF' },
  { name: 'Microsoft Teams', color: '#6264A7' },
  { name: 'Google Meet', color: '#00897B' },
]

export function PlatformStrip() {
  return (
    <section className="py-12 md:py-16 border-y border-white/5">
      <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10">
        <ScrollReveal className="flex flex-col sm:flex-row items-center justify-center gap-6 sm:gap-12">
          <span className="text-sm text-text-muted font-medium uppercase tracking-widest">
            Works with
          </span>
          <div className="flex items-center gap-8 md:gap-12">
            {PLATFORMS.map((platform) => (
              <div key={platform.name} className="flex items-center gap-2.5">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: platform.color }}
                  aria-hidden="true"
                />
                <span className="text-sm md:text-base text-white/70 font-medium">
                  {platform.name}
                </span>
              </div>
            ))}
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
