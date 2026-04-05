'use client'

import { Suspense, useState, useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing'
import { PerformanceMonitor, Preload } from '@react-three/drei'
import { ACESFilmicToneMapping } from 'three'
import { AICore } from '@/components/AICore'

function Scene() {
  const [dpr, setDpr] = useState(1.5)

  return (
    <Canvas
      gl={{
        antialias: true,
        toneMapping: ACESFilmicToneMapping,
        toneMappingExposure: 1.2,
      }}
      dpr={dpr}
      camera={{ position: [0, 0, 10], fov: 50 }}
      style={{ pointerEvents: 'none' }}
    >
      <PerformanceMonitor
        onIncline={() => setDpr(2)}
        onDecline={() => setDpr(1)}
      />
      <ambientLight intensity={0.3} />
      <pointLight position={[10, 10, 10]} intensity={0.5} />
      <Suspense fallback={null}>
        <AICore
          scale={0.7}
          pulse={0.6}
          showSatellites={true}
          kernelCount={2000}
          satelliteCount={400}
        />
      </Suspense>
      <EffectComposer>
        <Bloom
          luminanceThreshold={0.3}
          luminanceSmoothing={0.9}
          intensity={0.8}
        />
        <Vignette offset={0.3} darkness={0.6} />
      </EffectComposer>
      <Preload all />
    </Canvas>
  )
}

export function HeroCanvas() {
  const [supportsWebGL, setSupportsWebGL] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    try {
      const canvas = document.createElement('canvas')
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
      setSupportsWebGL(!!gl)
    } catch {
      setSupportsWebGL(false)
    }
  }, [])

  if (!mounted || !supportsWebGL) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="w-48 h-48 rounded-full bg-gradient-to-br from-warm-amber/20 to-ai-purple/20 blur-3xl" />
      </div>
    )
  }

  return <Scene />
}
