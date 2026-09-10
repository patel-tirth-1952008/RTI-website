"use client";
import React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Camera,
  Brain,
  Send,
  Shield,
  Clock,
  FileCheck,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { HeroScene } from "@/components/three/hero-scene";
import { useAuthStore } from "@/lib/store";

const features = [
  {
    icon: Camera,
    title: "Snap a Photo",
    desc: "Upload a photo of any civic issue — broken road, water leak, garbage pile.",
    color: "from-blue-500 to-cyan-500",
  },
  {
    icon: Brain,
    title: "AI Drafts Your RTI",
    desc: "Our AI analyzes the image, detects the issue, and generates a legally-sound RTI application.",
    color: "from-purple-500 to-pink-500",
  },
  {
    icon: Send,
    title: "Auto-File on Portal",
    desc: "We fill the government RTI portal form for you — no manual typing, no confusion.",
    color: "from-orange-500 to-red-500",
  },
  {
    icon: Shield,
    title: "Track & Appeal",
    desc: "Monitor your application status. If no reply in 30 days, file a First Appeal with one click.",
    color: "from-green-500 to-emerald-500",
  },
];

const stats = [
  { value: "30", label: "Day Response Guarantee", icon: Clock },
  { value: "₹0", label: "Platform Fee", icon: FileCheck },
  { value: "28+", label: "States Supported", icon: Users },
];

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore();

  return (
    <div className="relative overflow-hidden" style={{ backgroundColor: "#020617" }}>
      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(to bottom, #020617, rgba(23, 37, 84, 0.35), #020617)",
          }}
        />
        <HeroScene />

        <div className="relative z-10 max-w-5xl mx-auto px-4 text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <div
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-8"
              style={{
                backgroundColor: "rgba(59, 130, 246, 0.12)",
                border: "1px solid rgba(59, 130, 246, 0.25)",
              }}
            >
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-blue-300 text-sm font-medium">
                Powered by AI • 100% Free
              </span>
            </div>

            <h1 className="text-5xl md:text-7xl font-black leading-tight mb-6">
              <span className="text-white">Your Right to</span>
              <br />
              <span className="gradient-text">Information,</span>
              <br />
              <span className="text-white">Simplified.</span>
            </h1>

            <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
              Upload a photo of any civic problem. Our AI identifies the issue,
              drafts a powerful RTI application, and files it directly with the
              right government department — in minutes, not hours.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href={isAuthenticated ? "/new-rti" : "/register"}>
                <Button variant="primary" size="lg" glow>
                  File Your First RTI <ArrowRight className="ml-2 w-5 h-5" />
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button variant="outline" size="lg">
                  Track Existing RTI
                </Button>
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="mt-20 grid grid-cols-3 gap-6 max-w-lg mx-auto"
          >
            {stats.map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="text-2xl md:text-3xl font-black gradient-text">
                  {stat.value}
                </p>
                <p className="text-slate-500 text-xs mt-1">{stat.label}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="relative py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-bold mb-4 text-white">
              How <span className="gradient-text">RTI Sarthi</span> Works
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Four simple steps from photo to filed RTI application
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15 }}
              >
                <Card hover gradient className="h-full group">
                  <div
                    className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}
                  >
                    <feature.icon className="w-6 h-6 text-white" />
                  </div>
                  <div className="text-xs text-blue-400 font-bold mb-2">
                    STEP {i + 1}
                  </div>
                  <h3 className="text-white font-bold text-lg mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {feature.desc}
                  </p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <Card gradient className="py-16 px-8 relative overflow-hidden">
            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-bold mb-4 text-white">
                Ready to Hold the Government Accountable?
              </h2>
              <p className="text-slate-400 mb-8 max-w-lg mx-auto">
                Join thousands of citizens using RTI Sarthi to demand transparency
                and get results. It takes less than 5 minutes.
              </p>
              <Link href={isAuthenticated ? "/new-rti" : "/register"}>
                <Button variant="primary" size="lg" glow>
                  Start Now — It&apos;s Free{" "}
                  <ArrowRight className="ml-2 w-5 h-5" />
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}