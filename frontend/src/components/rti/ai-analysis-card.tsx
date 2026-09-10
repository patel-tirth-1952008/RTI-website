"use client";
import React from "react";
import { motion } from "framer-motion";
import { Brain, Building2, AlertTriangle, CheckCircle, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getCategoryIcon } from "@/lib/utils";

interface AIAnalysisCardProps {
  category: string;
  categoryConfidence?: number;
  department?: string;
  departmentConfidence?: number;
  imageScore?: number;
  questions: string[];
  severity?: string;
}

export function AIAnalysisCard({
  category,
  categoryConfidence,
  department,
  departmentConfidence,
  imageScore,
  questions,
  severity = "medium",
}: AIAnalysisCardProps) {
  const severityColors: Record<string, string> = {
    low: "text-green-400",
    medium: "text-yellow-400",
    high: "text-orange-400",
    critical: "text-red-400",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card gradient glow className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-white font-bold text-lg">AI Analysis Complete</h3>
            <p className="text-slate-400 text-sm">Your issue has been analyzed</p>
          </div>
          <Sparkles className="w-5 h-5 text-yellow-400 ml-auto animate-pulse" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-slate-900/50 rounded-xl p-4">
            <p className="text-slate-400 text-xs mb-1">Issue Category</p>
            <div className="flex items-center gap-2">
              <span className="text-2xl">{getCategoryIcon(category)}</span>
              <div>
                <p className="text-white font-semibold text-sm capitalize">
                  {category.replace(/_/g, " ")}
                </p>
                {categoryConfidence && (
                  <p className="text-blue-400 text-xs">
                    {Math.round(categoryConfidence * 100)}% confidence
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="bg-slate-900/50 rounded-xl p-4">
            <p className="text-slate-400 text-xs mb-1">Department</p>
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-green-400" />
              <div>
                <p className="text-white font-semibold text-sm">{department || "Auto-detected"}</p>
                {departmentConfidence && (
                  <p className="text-green-400 text-xs">
                    {Math.round(departmentConfidence * 100)}% match
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="bg-slate-900/50 rounded-xl p-4">
            <p className="text-slate-400 text-xs mb-1">Image & Severity</p>
            <div className="flex items-center gap-2">
              {imageScore && imageScore >= 0.7 ? (
                <CheckCircle className="w-5 h-5 text-green-400" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
              )}
              <div>
                <p className={cn("font-semibold text-sm", severityColors[severity])}>
                  {severity.toUpperCase()}
                </p>
                {imageScore !== undefined && (
                  <p className="text-slate-400 text-xs">
                    Photo: {Math.round((imageScore || 0) * 100)}% real
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        <div>
          <p className="text-slate-300 text-sm font-medium mb-2">
            AI-Generated RTI Questions ({questions.length}):
          </p>
          <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
            {questions.map((q, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
                className="flex items-start gap-2 text-sm"
              >
                <Badge variant="info" className="mt-0.5 shrink-0">{i + 1}</Badge>
                <p className="text-slate-300">{q}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

function cn(...classes: (string | undefined | boolean)[]) {
  return classes.filter(Boolean).join(" ");
}