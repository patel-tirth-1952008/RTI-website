"use client";
import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  glow?: boolean;
  gradient?: boolean;
  onClick?: () => void;
}

export function Card({
  children,
  className,
  hover = false,
  glow = false,
  gradient = false,
  onClick,
}: CardProps) {
  const style: React.CSSProperties = {
    background: gradient
      ? "linear-gradient(135deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95))"
      : "rgba(30, 41, 59, 0.55)",
    border: "1px solid rgba(51, 65, 85, 0.6)",
    backdropFilter: "blur(16px)",
    borderRadius: "16px",
    padding: "24px",
    boxShadow: glow ? "0 0 20px rgba(59,130,246,0.25)" : "none",
  };

  if (hover) {
    return (
      <motion.div
        whileHover={{ y: -4, scale: 1.01 }}
        transition={{ duration: 0.2 }}
        onClick={onClick}
        className={cn(onClick || hover ? "cursor-pointer" : "", className)}
        style={style}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <div
      onClick={onClick}
      className={cn(onClick ? "cursor-pointer" : "", className)}
      style={style}
    >
      {children}
    </div>
  );
}