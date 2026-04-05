'use client'

/**
 * AmbientBackground — Fixed layer behind all landing content.
 * Renders gradient wash orbs and floating particles.
 * All CSS-driven — no canvas, no JS animation loops.
 */
export function AmbientBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0" aria-hidden="true">
      {/* ── Large gradient wash orbs ── */}

      {/* Top-left: warm amber bloom */}
      <div
        className="ambient-orb"
        style={{
          width: '800px',
          height: '600px',
          top: '-10%',
          left: '-10%',
          background: 'radial-gradient(ellipse, rgba(13,148,136,0.03), transparent 70%)',
          filter: 'blur(80px)',
        }}
      />

      {/* Top-right: subtle purple */}
      <div
        className="ambient-orb"
        style={{
          width: '600px',
          height: '500px',
          top: '5%',
          right: '-5%',
          background: 'radial-gradient(ellipse, rgba(175,82,222,0.02), transparent 70%)',
          filter: 'blur(100px)',
        }}
      />

      {/* Mid-left: cyan accent (near features area) */}
      <div
        className="ambient-orb"
        style={{
          width: '500px',
          height: '500px',
          top: '35%',
          left: '-8%',
          background: 'radial-gradient(circle, rgba(37,99,235,0.02), transparent 60%)',
          filter: 'blur(100px)',
        }}
      />

      {/* Center: large soft amber (near pipeline) */}
      <div
        className="ambient-orb"
        style={{
          width: '900px',
          height: '600px',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(ellipse, rgba(13,148,136,0.03), transparent 65%)',
          filter: 'blur(120px)',
        }}
      />

      {/* Bottom-right: purple bloom (near pricing) */}
      <div
        className="ambient-orb"
        style={{
          width: '700px',
          height: '500px',
          bottom: '10%',
          right: '-5%',
          background: 'radial-gradient(ellipse, rgba(175,82,222,0.02), transparent 65%)',
          filter: 'blur(100px)',
        }}
      />

      {/* Bottom-center: warm amber (near CTA) */}
      <div
        className="ambient-orb"
        style={{
          width: '600px',
          height: '400px',
          bottom: '-5%',
          left: '40%',
          background: 'radial-gradient(ellipse, rgba(37,99,235,0.02), transparent 60%)',
          filter: 'blur(100px)',
        }}
      />

      {/* ── Floating particles ── */}
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{
            width: `${p.size}px`,
            height: `${p.size}px`,
            left: `${p.x}%`,
            bottom: `-${p.size}px`,
            backgroundColor: p.color,
            animation: `${p.anim} ${p.duration}s ${p.delay}s linear infinite`,
            opacity: 0,
          }}
        />
      ))}
    </div>
  )
}

const PARTICLES = [
  { x: 8,  size: 2, color: 'rgba(13,148,136,0.12)', anim: 'float-up',      duration: 18, delay: 0 },
  { x: 22, size: 1.5, color: 'rgba(0,0,0,0.03)',   anim: 'float-up-slow', duration: 24, delay: 3 },
  { x: 38, size: 2, color: 'rgba(37,99,235,0.06)', anim: 'float-up',      duration: 20, delay: 6 },
  { x: 52, size: 1, color: 'rgba(0,0,0,0.03)',     anim: 'float-up-slow', duration: 28, delay: 1 },
  { x: 65, size: 2.5, color: 'rgba(13,148,136,0.12)', anim: 'float-up',    duration: 22, delay: 8 },
  { x: 78, size: 1.5, color: 'rgba(37,99,235,0.06)', anim: 'float-up-slow', duration: 26, delay: 4 },
  { x: 91, size: 2, color: 'rgba(0,0,0,0.03)',     anim: 'float-up',      duration: 20, delay: 10 },
  { x: 15, size: 1, color: 'rgba(37,99,235,0.06)', anim: 'float-up-slow', duration: 30, delay: 12 },
  { x: 45, size: 1.5, color: 'rgba(13,148,136,0.12)', anim: 'float-up',    duration: 25, delay: 7 },
  { x: 85, size: 2, color: 'rgba(0,0,0,0.03)',     anim: 'float-up-slow', duration: 22, delay: 2 },
]
