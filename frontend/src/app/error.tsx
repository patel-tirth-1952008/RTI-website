"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global UI Error Caught:", error);
  }, [error]);

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-4">
      <Card gradient glow className="max-w-md w-full text-center p-8 space-y-4">
        <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-white">Something Went Wrong</h2>
        <p className="text-slate-400 text-sm">
          An unexpected error occurred in the user interface. Please try again.
        </p>
        <Button variant="primary" onClick={() => reset()} className="w-full">
          Reload Page
        </Button>
      </Card>
    </div>
  );
}