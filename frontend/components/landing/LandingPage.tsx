'use client'

import { Navbar } from './Navbar'
import { Footer } from './Footer'
import { AmbientBackground } from './AmbientBackground'
import { HeroSection } from './sections/HeroSection'
import { JoiningSection } from './sections/JoiningSection'
import { AskingSection } from './sections/AskingSection'
import { ThinkingSection } from './sections/ThinkingSection'
import { BentoGridSection } from './sections/BentoGridSection'
import { SummarySection } from './sections/SummarySection'
import { ComparisonSection } from './sections/ComparisonSection'
import { PricingSection } from './sections/PricingSection'
import { FinalCTASection } from './sections/FinalCTASection'

export function LandingPage() {
  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-white focus:text-black focus:rounded focus:shadow-lg"
      >
        Skip to main content
      </a>

      <AmbientBackground />
      <Navbar />

      <main id="main-content" tabIndex={-1} className="relative z-[1]">
        <HeroSection />
        <JoiningSection />
        <AskingSection />
        <ThinkingSection />
        <BentoGridSection />
        <SummarySection />
        <ComparisonSection />
        <PricingSection />
        <FinalCTASection />
      </main>

      <Footer />
    </>
  )
}
