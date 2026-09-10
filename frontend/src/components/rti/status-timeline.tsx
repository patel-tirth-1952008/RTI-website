"use client";
import React from "react";
import { motion } from "framer-motion";
import { CheckCircle, Clock, AlertCircle, FileText, Send, Eye, Gavel } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimelineStep {
  label: string;
  status: "completed" | "current" | "upcoming" | "failed";
  date?: string;
  description?: string;
}

interface StatusTimelineProps {
  steps: TimelineStep[];
}

const icons = {
  completed: CheckCircle,
  current: Clock,
  upcoming: AlertCircle,
  failed: AlertCircle,
};

export function StatusTimeline({ steps }: StatusTimelineProps) {
  return (
    <div className="relative">
      {steps.map((step, index) => {
        const Icon = icons[step.status];
        const isLast = index === steps.length - 1;

        return (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.15 }}
            className="flex gap-4"
          >
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center border-2 shrink-0",
                  step.status === "completed" && "bg-green-500/20 border-green-500 text-green-400",
                  step.status === "current" && "bg-blue-500/20 border-blue-500 text-blue-400 animate-pulse",
                  step.status === "upcoming" && "bg-slate-800 border-slate-600 text-slate-500",
                  step.status === "failed" && "bg-red-500/20 border-red-500 text-red-400"
                )}
              >
                <Icon className="w-5 h-5" />
              </div>
              {!isLast && (
                <div
                  className={cn(
                    "w-0.5 h-16",
                    step.status === "completed" ? "bg-green-500" : "bg-slate-700"
                  )}
                />
              )}
            </div>

            <div className={cn("pb-8", isLast && "pb-0")}>
              <p
                className={cn(
                  "font-semibold text-sm",
                  step.status === "completed" && "text-green-400",
                  step.status === "current" && "text-blue-400",
                  step.status === "upcoming" && "text-slate-500",
                  step.status === "failed" && "text-red-400"
                )}
              >
                {step.label}
              </p>
              {step.date && <p className="text-slate-500 text-xs mt-0.5">{step.date}</p>}
              {step.description && <p className="text-slate-400 text-sm mt-1">{step.description}</p>}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}