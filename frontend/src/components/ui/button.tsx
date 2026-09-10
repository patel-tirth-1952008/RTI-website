"use client";
import React from "react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  glow?: boolean;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  glow = false,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed border-0 cursor-pointer";

  const variants: Record<string, React.CSSProperties> = {
    primary: {
      background: "linear-gradient(to right, #2563eb, #9333ea)",
      color: "#fff",
      boxShadow: glow
        ? "0 0 20px rgba(59,130,246,0.45)"
        : "0 10px 25px rgba(37,99,235,0.25)",
    },
    secondary: {
      background: "linear-gradient(to right, #334155, #1e293b)",
      color: "#fff",
    },
    outline: {
      background: "transparent",
      color: "#60a5fa",
      border: "2px solid #3b82f6",
    },
    ghost: {
      background: "transparent",
      color: "#94a3b8",
    },
    danger: {
      background: "linear-gradient(to right, #dc2626, #b91c1c)",
      color: "#fff",
    },
  };

  const sizes: Record<string, string> = {
    sm: "px-3 py-1.5 text-sm rounded-lg",
    md: "px-5 py-2.5 text-sm rounded-xl",
    lg: "px-8 py-3.5 text-base rounded-xl",
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className={cn(base, sizes[size], className)}
      style={variants[variant]}
      disabled={disabled || loading}
      {...(props as any)}
    >
      {loading && (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </motion.button>
  );
}