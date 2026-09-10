"use client";
import React, { useState } from "react";
import { motion } from "framer-motion";
import { FileText, Edit3, Check, Copy } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import toast from "react-hot-toast";

interface RTIPreviewProps {
  subject: string;
  body: string;
  onBodyChange: (newBody: string) => void;
  departmentName?: string;
  pioName?: string;
}

export function RTIPreview({
  subject,
  body,
  onBodyChange,
  departmentName,
  pioName,
}: RTIPreviewProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedBody, setEditedBody] = useState(body);

  const handleSave = () => {
    onBodyChange(editedBody);
    setIsEditing(false);
    toast.success("RTI application text updated!");
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
    toast.success("RTI text copied to clipboard!");
  };

  return (
    <Card gradient className="space-y-4">
      <div className="flex items-center justify-between border-b border-slate-700/50 pb-4">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-blue-400" />
          <h3 className="text-white font-bold text-lg">Generated RTI Draft</h3>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            <Copy className="w-4 h-4 mr-1" /> Copy
          </Button>
          {isEditing ? (
            <Button variant="primary" size="sm" onClick={handleSave}>
              <Check className="w-4 h-4 mr-1" /> Save
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
              <Edit3 className="w-4 h-4 mr-1" /> Edit Text
            </Button>
          )}
        </div>
      </div>

      <div className="bg-slate-900/60 p-4 rounded-xl space-y-3 font-mono text-sm border border-slate-700/30">
        <div>
          <span className="text-slate-500 font-sans text-xs uppercase font-bold tracking-wider">
            Subject:
          </span>
          <p className="text-blue-300 font-semibold mt-0.5 font-sans">{subject}</p>
        </div>

        <div>
          <span className="text-slate-500 font-sans text-xs uppercase font-bold tracking-wider">
            Addressed To:
          </span>
          <p className="text-slate-300 font-sans text-xs mt-0.5">
            {pioName || "Public Information Officer"}, {departmentName || "Concerned Authority"}
          </p>
        </div>

        <div className="pt-2 border-t border-slate-800">
          <span className="text-slate-500 font-sans text-xs uppercase font-bold tracking-wider mb-2 block">
            Application Body:
          </span>
          {isEditing ? (
            <textarea
              value={editedBody}
              onChange={(e) => setEditedBody(e.target.value)}
              className="w-full h-80 bg-slate-950 border border-blue-500/50 rounded-lg p-3 text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs leading-relaxed"
            />
          ) : (
            <pre className="whitespace-pre-wrap text-slate-300 text-xs leading-relaxed max-h-80 overflow-y-auto pr-2 font-mono">
              {body}
            </pre>
          )}
        </div>
      </div>
    </Card>
  );
}