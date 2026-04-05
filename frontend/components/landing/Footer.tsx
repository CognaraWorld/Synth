'use client'

const FOOTER_LINKS = [
  {
    heading: 'Product',
    links: [
      { label: 'Features', href: '#demo' },
      { label: 'Pricing', href: '#pricing' },
      { label: 'Book a Demo', href: '#book-demo' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { label: 'About', href: '#' },
      { label: 'Blog', href: '#' },
      { label: 'Contact', href: '#book-demo' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { label: 'Privacy Policy', href: '#' },
      { label: 'Terms of Service', href: '#' },
    ],
  },
]

export function Footer() {
  return (
    <footer className="border-t border-[#EAE8E4] bg-[#FAF9F6]">
      <div className="max-w-7xl mx-auto px-4 md:px-8 lg:px-10 py-12 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-6 h-6 rounded-md cta-gradient" aria-hidden="true" />
              <span className="text-base font-bold text-[#1D1D1F]">Cognara</span>
            </div>
            <p className="text-sm text-[#6E6E73] leading-relaxed max-w-xs">
              The AI teammate that knows when to speak.
            </p>
          </div>

          {FOOTER_LINKS.map((group) => (
            <nav key={group.heading} aria-label={`${group.heading} navigation`}>
              <h3 className="text-xs font-semibold text-[#86868B] uppercase tracking-widest mb-4">
                {group.heading}
              </h3>
              <ul className="space-y-2.5">
                {group.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-[#6E6E73] hover:text-[#1D1D1F] transition-colors"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-12 pt-8 border-t border-black/[0.04] flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-[#AEAEB2]">
            &copy; {new Date().getFullYear()} Cognara. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <a href="#" className="text-xs text-[#AEAEB2] hover:text-[#86868B] transition-colors">Twitter</a>
            <a href="#" className="text-xs text-[#AEAEB2] hover:text-[#86868B] transition-colors">LinkedIn</a>
          </div>
        </div>
      </div>
    </footer>
  )
}
