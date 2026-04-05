'use client'

import { useEffect, useCallback } from 'react'
import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useNarrativeStore } from '@/stores/narrativeStore'

gsap.registerPlugin(ScrollTrigger)

/**
 * Lenis smooth scroll → GSAP ScrollTrigger → Zustand store.
 * Also tracks normalised cursor position for magnetic interactions.
 */
export function useScrollSync() {
  const handleMouse = useCallback((e: MouseEvent) => {
    useNarrativeStore.getState().setCursor(
      (e.clientX / window.innerWidth) * 2 - 1,
      -(e.clientY / window.innerHeight) * 2 + 1
    )
  }, [])

  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.3,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      touchMultiplier: 1.5,
    })

    lenis.on('scroll', ScrollTrigger.update)
    const tick = (time: number) => lenis.raf(time * 1000)
    gsap.ticker.add(tick)
    gsap.ticker.lagSmoothing(0)

    ScrollTrigger.create({
      trigger: '#narrative-scroll',
      start: 'top top',
      end: 'bottom bottom',
      scrub: 0.3,
      onUpdate: (self) => useNarrativeStore.getState().updateProgress(self.progress),
    })

    window.addEventListener('mousemove', handleMouse)

    return () => {
      window.removeEventListener('mousemove', handleMouse)
      gsap.ticker.remove(tick)
      ScrollTrigger.killAll()
      lenis.destroy()
    }
  }, [handleMouse])
}
