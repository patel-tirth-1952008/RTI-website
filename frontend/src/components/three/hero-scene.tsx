"use client";
import React, { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sphere, Box, Torus } from "@react-three/drei";
import * as THREE from "three";

function FloatingDocument({ position, color, speed }: { position: [number, number, number]; color: string; speed: number }) {
  const meshRef = useRef<THREE.Mesh>(null!);

  useFrame((state) => {
    meshRef.current.rotation.x = Math.sin(state.clock.elapsedTime * speed) * 0.3;
    meshRef.current.rotation.y = state.clock.elapsedTime * speed * 0.5;
    meshRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime * speed) * 0.3;
  });

  return (
    <Float speed={speed} rotationIntensity={0.5} floatIntensity={1}>
      <Box ref={meshRef} args={[0.8, 1.1, 0.05]} position={position}>
        <meshStandardMaterial color={color} transparent opacity={0.8} />
      </Box>
    </Float>
  );
}

function GlowingSphere({ position, color, size }: { position: [number, number, number]; color: string; size: number }) {
  return (
    <Float speed={2} floatIntensity={2}>
      <Sphere args={[size, 32, 32]} position={position}>
        <meshBasicMaterial color={color} transparent opacity={0.4} />
      </Sphere>
    </Float>
  );
}

function ParticleRing() {
  const ref = useRef<THREE.Points>(null!);
  const count = 300;

  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const radius = 3 + Math.random() * 2;
      pos[i * 3] = Math.cos(angle) * radius;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 2;
      pos[i * 3 + 2] = Math.sin(angle) * radius;
    }
    return pos;
  }, []);

  useFrame((state) => {
    ref.current.rotation.y = state.clock.elapsedTime * 0.05;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial size={0.03} color="#60a5fa" transparent opacity={0.5} sizeAttenuation />
    </points>
  );
}

export function HeroScene() {
  return (
    <div className="absolute inset-0 z-0 opacity-60">
      <Canvas camera={{ position: [0, 0, 6], fov: 60 }} dpr={[1, 1.5]}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={1} color="#60a5fa" />
        
        <FloatingDocument position={[-2.5, 1, -1]} color="#3b82f6" speed={0.8} />
        <FloatingDocument position={[2.5, -0.5, -2]} color="#8b5cf6" speed={1.2} />
        <FloatingDocument position={[0, 2, -3]} color="#f97316" speed={0.6} />

        <GlowingSphere position={[-3, -1, -2]} color="#3b82f6" size={0.6} />
        <GlowingSphere position={[3, 1.5, -3]} color="#8b5cf6" size={0.4} />

        <Torus args={[2.5, 0.02, 16, 100]} position={[0, 0, -2]} rotation={[Math.PI / 3, 0, 0]}>
          <meshBasicMaterial color="#3b82f6" transparent opacity={0.3} />
        </Torus>

        <ParticleRing />
      </Canvas>
    </div>
  );
}