'use client'

interface SectionHeaderProps {
  number?: string
  heading: string
  subtitle?: string
  align?: 'left' | 'center'
}

export function SectionHeader({ number, heading, subtitle, align = 'center' }: SectionHeaderProps) {
  const alignClass = align === 'center' ? 'text-center' : 'text-left'

  return (
    <div className={`${alignClass} mb-12 md:mb-16`}>
      {number && (
        <span className="inline-block font-mono text-sm text-warm-amber tracking-widest uppercase mb-4">
          {number}
        </span>
      )}
      <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white leading-tight tracking-tight">
        {heading}
      </h2>
      {subtitle && (
        <p className="mt-4 text-lg text-text-muted max-w-2xl mx-auto leading-relaxed">
          {subtitle}
        </p>
      )}
    </div>
  )
}
