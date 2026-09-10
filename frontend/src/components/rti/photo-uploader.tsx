"use client";
import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, Upload, X, CheckCircle, AlertTriangle, Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PhotoUploaderProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  onRemove: () => void;
  fraudScore?: number | null;
}

export function PhotoUploader({ onFileSelect, selectedFile, onRemove, fraudScore }: PhotoUploaderProps) {
  const [preview, setPreview] = useState<string | null>(null);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (file) {
        onFileSelect(file);
        const reader = new FileReader();
        reader.onload = () => setPreview(reader.result as string);
        reader.readAsDataURL(file);
      }
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpeg", ".jpg", ".png", ".webp"] },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
  });

  const getFraudColor = () => {
    if (!fraudScore) return "border-slate-600";
    if (fraudScore >= 0.7) return "border-green-500";
    if (fraudScore >= 0.5) return "border-yellow-500";
    return "border-red-500";
  };

  return (
    <div className="w-full">
      <AnimatePresence mode="wait">
        {selectedFile && preview ? (
          <motion.div
            key="preview"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className={cn("relative rounded-2xl overflow-hidden border-2", getFraudColor())}
          >
            <img src={preview} alt="Issue" className="w-full h-64 object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
            <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between">
              <div>
                <p className="text-white font-medium text-sm">{selectedFile.name}</p>
                <p className="text-slate-300 text-xs">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                {fraudScore !== null && fraudScore !== undefined && (
                  <div className="flex items-center gap-1 mt-1">
                    {fraudScore >= 0.7 ? (
                      <CheckCircle className="w-3 h-3 text-green-400" />
                    ) : (
                      <AlertTriangle className="w-3 h-3 text-yellow-400" />
                    )}
                    <span className={cn("text-xs", fraudScore >= 0.7 ? "text-green-400" : "text-yellow-400")}>
                      Authenticity: {Math.round(fraudScore * 100)}%
                    </span>
                  </div>
                )}
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); onRemove(); setPreview(null); }}
                className="p-2 bg-red-500/80 rounded-full hover:bg-red-500 transition-colors"
              >
                <X className="w-4 h-4 text-white" />
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="dropzone"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all",
              isDragActive
                ? "border-blue-400 bg-blue-500/10"
                : "border-slate-600 hover:border-blue-500/50 hover:bg-slate-800/30"
            )}
          >
            <input {...getInputProps()} />
            <motion.div
              animate={isDragActive ? { scale: 1.1 } : { scale: 1 }}
              className="flex flex-col items-center gap-4"
            >
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center">
                {isDragActive ? (
                  <Upload className="w-8 h-8 text-blue-400" />
                ) : (
                  <Camera className="w-8 h-8 text-slate-400" />
                )}
              </div>
              <div>
                <p className="text-white font-semibold">
                  {isDragActive ? "Drop the photo here" : "Upload a photo of the issue"}
                </p>
                <p className="text-slate-400 text-sm mt-1">
                  Drag & drop or click to browse • JPG, PNG up to 10MB
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <ImageIcon className="w-3 h-3" />
                <span>AI will analyze the image for authenticity & issue type</span>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}