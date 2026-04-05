import { create } from 'zustand'

/* ═══════════════════════════════════════════════════════════
   Narrative Store — scroll progress drives the entire world

   World Z-axis map:
     Act 1  Awakening       z =    0
     Act 2  Joining          z =  -40
     Act 3  Listening        z = -100
     Act 4  Transcribing     z = -180
     Act 5  Understanding    z = -260
     Act 6  Answering        z = -340
     Act 7  Synthesis        z = -450
   ═══════════════════════════════════════════════════════════ */

export const ACT_COUNT = 7
export const ACT_SIZE = 1 / ACT_COUNT

export interface NarrativeState {
  scrollProgress: number
  currentAct: number
  cursorX: number
  cursorY: number
  isLoaded: boolean

  updateProgress: (val: number) => void
  setCursor: (x: number, y: number) => void
  setIsLoaded: (v: boolean) => void
}

function progressToAct(p: number): number {
  if (p >= 1) return ACT_COUNT
  return Math.floor(p * ACT_COUNT) + 1
}

export const useNarrativeStore = create<NarrativeState>()((set) => ({
  scrollProgress: 0,
  currentAct: 1,
  cursorX: 0,
  cursorY: 0,
  isLoaded: false,

  updateProgress: (val) => set({ scrollProgress: val, currentAct: progressToAct(val) }),
  setCursor: (x, y) => set({ cursorX: x, cursorY: y }),
  setIsLoaded: (v) => set({ isLoaded: v }),
}))

/** Local progress [0,1] within a specific act */
export function getActLocal(scrollProgress: number, act: number): number {
  const start = (act - 1) * ACT_SIZE
  return Math.max(0, Math.min(1, (scrollProgress - start) / ACT_SIZE))
}

/** Text fade: in 0→0.12, hold 0.12→0.78, out 0.78→1 */
export function getActTextOpacity(scrollProgress: number, act: number): number {
  const t = getActLocal(scrollProgress, act)
  if (t <= 0 || t >= 1) return 0
  if (t < 0.12) return t / 0.12
  if (t > 0.78) return 1 - (t - 0.78) / 0.22
  return 1
}
