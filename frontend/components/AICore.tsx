'use client'

import { useRef, useMemo, useEffect } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useNarrativeStore } from '@/stores/narrativeStore'
import { kernelVertex, kernelFragment } from '@/shaders/corePulse'
import { shellVertex, shellFragment } from '@/shaders/neuralShell'
import { orbitVertex, orbitFragment } from '@/shaders/orbitSignals'

/* ═══════════════════════════════════════════════════════════
   AICore — The protagonist. Present in every act.

   3 layers:
     1. Kernel    — 3000 noise-displaced particles (Points)
     2. Shell     — barycentric icosahedron lattice (Mesh)
     3. Satellites — 600 instanced tetrahedrons (InstancedMesh)

   Props control scale, intensity, and satellite visibility
   so each act can tune the core's appearance.
   ═══════════════════════════════════════════════════════════ */

interface AICoreProps {
  scale?: number
  pulse?: number
  showSatellites?: boolean
  kernelCount?: number
  satelliteCount?: number
}

/* ── Layer 1: Kernel Particles ── */
function Kernel({ count = 3000, pulse = 1 }: { count?: number; pulse?: number }) {
  const matRef = useRef<THREE.ShaderMaterial>(null)
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry()
    const pos = new Float32Array(count * 3)
    const sizes = new Float32Array(count)
    const phases = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const th = Math.random() * Math.PI * 2
      const ph = Math.acos(2 * Math.random() - 1)
      const r = Math.pow(Math.random(), 1.8) * 3
      pos[i*3]=r*Math.sin(ph)*Math.cos(th); pos[i*3+1]=r*Math.sin(ph)*Math.sin(th); pos[i*3+2]=r*Math.cos(ph)
      sizes[i] = Math.random() * 2.5 + 0.5
      phases[i] = Math.random() * Math.PI * 2
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    g.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1))
    g.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1))
    return g
  }, [count])

  const uniforms = useMemo(() => ({
    uTime: { value: 0 }, uPulse: { value: 0.5 },
    uPixelRatio: { value: typeof window !== 'undefined' ? Math.min(window.devicePixelRatio, 2) : 1 },
    uColor: { value: new THREE.Color('#00F0FF') }, uMouse: { value: new THREE.Vector2() },
  }), [])

  useFrame((_, d) => {
    if (!matRef.current) return
    const s = useNarrativeStore.getState()
    matRef.current.uniforms.uTime.value += d
    matRef.current.uniforms.uPulse.value = pulse
    matRef.current.uniforms.uMouse.value.set(s.cursorX, s.cursorY)
  })

  return (
    <points geometry={geo}>
      <shaderMaterial ref={matRef} vertexShader={kernelVertex} fragmentShader={kernelFragment}
        uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
    </points>
  )
}

/* ── Layer 2: Neural Shell ── */
function Shell({ pulse = 1 }: { pulse?: number }) {
  const matRef = useRef<THREE.ShaderMaterial>(null)
  const meshRef = useRef<THREE.Mesh>(null)
  const geo = useMemo(() => {
    const base = new THREE.IcosahedronGeometry(3.5, 2).toNonIndexed()
    const count = base.attributes.position.count
    const bary = new Float32Array(count * 3)
    for (let i = 0; i < count; i += 3) {
      bary[i*3]=1;bary[i*3+1]=0;bary[i*3+2]=0
      bary[(i+1)*3]=0;bary[(i+1)*3+1]=1;bary[(i+1)*3+2]=0
      bary[(i+2)*3]=0;bary[(i+2)*3+1]=0;bary[(i+2)*3+2]=1
    }
    base.setAttribute('aBarycentric', new THREE.BufferAttribute(bary, 3))
    base.computeVertexNormals()
    return base
  }, [])

  const uniforms = useMemo(() => ({
    uTime: { value: 0 }, uColor: { value: new THREE.Color('#00F0FF') },
    uPulseAmp: { value: 0.3 }, uWaveFreq: { value: 10 }, uBaseAlpha: { value: 0.2 },
  }), [])

  useFrame((_, d) => {
    if (!matRef.current || !meshRef.current) return
    matRef.current.uniforms.uTime.value += d
    matRef.current.uniforms.uPulseAmp.value = pulse * 0.8
    matRef.current.uniforms.uBaseAlpha.value = 0.12 + pulse * 0.2
    meshRef.current.rotation.y += d * 0.03
    meshRef.current.rotation.z += d * 0.012
  })

  return (
    <mesh ref={meshRef} geometry={geo}>
      <shaderMaterial ref={matRef} vertexShader={shellVertex} fragmentShader={shellFragment}
        uniforms={uniforms} transparent side={THREE.DoubleSide} depthWrite={false} blending={THREE.AdditiveBlending} />
    </mesh>
  )
}

/* ── Layer 3: Data Satellites ── */
function Satellites({ count = 600 }: { count?: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const matRef = useRef<THREE.ShaderMaterial>(null)

  const { params, speed } = useMemo(() => {
    const p = new Float32Array(count * 3), s = new Float32Array(count * 2)
    for (let i = 0; i < count; i++) {
      p[i*3]=4+Math.random()*5.5; p[i*3+1]=3+Math.random()*4.5; p[i*3+2]=Math.random()*Math.PI*2
      s[i*2]=0.15+Math.random()*0.55; s[i*2+1]=Math.random()*Math.PI
    }
    return { params: p, speed: s }
  }, [count])

  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uColor: { value: new THREE.Color('#00F0FF') } }), [])

  useEffect(() => {
    if (!meshRef.current) return
    meshRef.current.geometry.setAttribute('aOrbitParams', new THREE.InstancedBufferAttribute(params, 3))
    meshRef.current.geometry.setAttribute('aOrbitSpeed', new THREE.InstancedBufferAttribute(speed, 2))
    const d = new THREE.Object3D()
    for (let i = 0; i < count; i++) {
      d.position.set(0,0,0)
      d.rotation.set(Math.random()*6.28,Math.random()*6.28,Math.random()*6.28)
      d.updateMatrix(); meshRef.current.setMatrixAt(i, d.matrix)
    }
    meshRef.current.instanceMatrix.needsUpdate = true
  }, [count, params, speed])

  useFrame((_, d) => { if (matRef.current) matRef.current.uniforms.uTime.value += d })

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
      <tetrahedronGeometry args={[0.06, 0]} />
      <shaderMaterial ref={matRef} vertexShader={orbitVertex} fragmentShader={orbitFragment}
        uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending} />
    </instancedMesh>
  )
}

/* ── AICore export ── */
export function AICore({ scale = 1, pulse = 1, showSatellites = true, kernelCount = 3000, satelliteCount = 600 }: AICoreProps) {
  return (
    <group scale={scale}>
      <pointLight color="#00F0FF" intensity={3 + pulse * 3} distance={18} decay={2} />
      <Kernel count={kernelCount} pulse={pulse} />
      <Shell pulse={pulse} />
      {showSatellites && <Satellites count={satelliteCount} />}
    </group>
  )
}
