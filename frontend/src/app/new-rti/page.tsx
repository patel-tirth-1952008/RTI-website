"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Send,
  CheckCircle2,
  ExternalLink,
  Loader2,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { PhotoUploader } from "@/components/rti/photo-uploader";
import { AIAnalysisCard } from "@/components/rti/ai-analysis-card";
import { RTIPreview } from "@/components/rti/rti-preview";
import { rtiAPI, filingAPI } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { RTIGenerateResponse } from "@/types";
import toast from "react-hot-toast";

export default function NewRTIPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [photo, setPhoto] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");

  const [generating, setGenerating] = useState(false);
  const [draft, setDraft] = useState<RTIGenerateResponse | null>(null);
  const [editedBody, setEditedBody] = useState("");

  const [filing, setFiling] = useState(false);
  const [filingStage, setFilingStage] = useState<string>("Initializing portal connection...");
  const [filingError, setFilingError] = useState<string | null>(null);
  const [filingResult, setFilingResult] = useState<any>(null);

  useEffect(() => {
    if (user) {
      setCity(user.city || "");
      setState(user.state || "Gujarat");
    }
  }, [user]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description || !location) {
      toast.error("Please fill in location and issue description.");
      return;
    }

    setGenerating(true);
    const formData = new FormData();
    formData.append("issue_description", description);
    formData.append("issue_location", location);
    formData.append("issue_city", city || user?.city || "Ahmedabad");
    formData.append("issue_state", state || user?.state || "Gujarat");

    if (photo) {
      formData.append("image", photo);
    }

    try {
      const res = await rtiAPI.generate(formData);
      setDraft(res.data);
      setEditedBody(res.data.generated_body);
      setStep(2);
      toast.success("RTI application generated successfully!");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to generate RTI.");
    } finally {
      setGenerating(false);
    }
  };

  const handleFileOnPortal = async () => {
    if (!draft) return;
    setFiling(true);
    setFilingError(null);
    setFilingStage("Connecting to Gujarat RTI Portal (onlinerti.gujarat.gov.in)...");

    const stageTimer1 = setTimeout(() => {
      setFilingStage("Navigating Login & Solving Math CAPTCHA...");
    }, 4000);

    const stageTimer2 = setTimeout(() => {
      setFilingStage("Selecting Target Department & Entering RTI Text...");
    }, 10000);

    const stageTimer3 = setTimeout(() => {
      setFilingStage("Generating ₹10 Government Treasury / Payment Link...");
    }, 18000);

    try {
      const payload = {
        tracking_number: draft.tracking_number,
        applicant_name: user?.full_name || user?.name || "Citizen Applicant",
        applicant_email: user?.email || "citizen@example.com",
        applicant_mobile: user?.mobile || user?.phone || "9876543210",
        applicant_address: user?.address || `${location}, ${city || "Ahmedabad"}, ${state || "Gujarat"}`,
        applicant_pincode: user?.pincode || "380001",
        gender: (user as any)?.gender || "male",
        education: (user as any)?.education || "graduate",
        area_type: (user as any)?.area_type || "urban",
        consent_to_file: true,
        modified_rti_text: editedBody,
      };

      const res = await filingAPI.submit(payload);

      // Verify portal automation result
      if (res.data && res.data.success === false) {
        setFilingError(res.data.message || "Could not reach government portal.");
        toast.error("Portal automation encountered an error.");
        return; // Stay on Step 2 so user can retry or adjust input
      }

      // Success
      setFilingResult(res.data);
      setStep(3);
      toast.success("RTI Automated Filing Completed!");
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMessage = typeof detail === "string" ? detail : "Filing request failed. Please retry.";
      setFilingError(errorMessage);
      toast.error(errorMessage);
    } finally {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setFiling(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      {/* Step Indicator */}
      <div className="flex items-center justify-between mb-8 max-w-md mx-auto">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm transition-all ${
                step >= s
                  ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg shadow-blue-500/30"
                  : "bg-slate-800 text-slate-500"
              }`}
            >
              {s}
            </div>
            <span className={`text-xs font-semibold ${step >= s ? "text-white" : "text-slate-500"}`}>
              {s === 1 ? "Issue & Photo" : s === 2 ? "Review Draft" : "Filed & Payment"}
            </span>
          </div>
        ))}
      </div>

      {/* Automated Filing Progress Modal Overlay */}
      {filing && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-8 max-w-md w-full space-y-6 shadow-2xl">
            <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
              <Loader2 className="w-16 h-16 text-blue-500 animate-spin" />
              <ShieldCheck className="w-8 h-8 text-blue-400 absolute" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-white font-display">Automating Official Portal</h3>
              <p className="text-xs text-slate-400 mt-1">Executing Gujarat RTI Portal Automation Pipeline</p>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700">
              <p className="text-sm font-mono text-blue-400 font-medium animate-pulse">{filingStage}</p>
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Playwright agent is filling form fields on <span className="text-slate-300">onlinerti.gujarat.gov.in</span>.
              Please stay on this page.
            </p>
          </div>
        </div>
      )}

      <AnimatePresence mode="wait">
        {/* STEP 1: Describe & Upload Photo */}
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
          >
            <Card gradient className="p-8">
              <div className="mb-6">
                <h1 className="text-2xl font-bold font-display text-white">Describe the Issue</h1>
                <p className="text-slate-400 text-sm">
                  Upload a photo of the damaged road, leak, or garbage, and explain the issue below.
                </p>
              </div>

              <form onSubmit={handleGenerate} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Evidence Photo (Optional but Recommended)
                  </label>
                  <PhotoUploader
                    onFileSelect={(file) => setPhoto(file)}
                    selectedFile={photo}
                    onRemove={() => setPhoto(null)}
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Input
                    label="Specific Location / Landmark"
                    placeholder="e.g. Main road from Nikol Gam to Raspan Cross Road"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    required
                  />

                  <Input
                    label="City / District"
                    placeholder="Ahmedabad"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">
                    What is the problem? (Duration, severity, past complaints)
                  </label>
                  <textarea
                    rows={4}
                    className="w-full bg-slate-800/50 border border-slate-700 rounded-xl p-4 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm leading-relaxed"
                    placeholder="e.g. The 200m stretch of road has huge potholes since 2 years. Water accumulates during rains, causing daily traffic jams. No repair work has been done despite repeated requests."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    required
                  />
                </div>

                <Button type="submit" variant="primary" size="lg" className="w-full" loading={generating} glow>
                  <Sparkles className="w-5 h-5 mr-2" /> Generate RTI with AI
                </Button>
              </form>
            </Card>
          </motion.div>
        )}

        {/* STEP 2: Review AI Analysis & Submit to Portal */}
        {step === 2 && draft && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="space-y-6"
          >
            {filingError && (
              <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-xl flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <div className="text-sm text-red-200">
                  <p className="font-semibold">Automated Filing Failed</p>
                  <p className="text-xs text-red-300 mt-1">{filingError}</p>
                </div>
              </div>
            )}

            <AIAnalysisCard
              category={draft.category}
              categoryConfidence={draft.ai_category_confidence}
              department={draft.department_name}
              departmentConfidence={draft.ai_department_confidence}
              imageScore={draft.image_authenticity_score}
              questions={draft.generated_questions}
            />

            <RTIPreview
              subject={draft.generated_subject}
              body={editedBody}
              onBodyChange={setEditedBody}
              departmentName={draft.department_name}
              pioName={draft.pio_name}
            />

            <div className="flex gap-4">
              <Button variant="secondary" onClick={() => setStep(1)} className="w-1/3">
                <ArrowLeft className="w-4 h-4 mr-2" /> Back
              </Button>
              <Button
                variant="primary"
                onClick={handleFileOnPortal}
                loading={filing}
                className="w-2/3"
                glow
              >
                {filingError ? (
                  <>
                    <RefreshCw className="w-5 h-5 mr-2" /> Retry Submission to Portal
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5 mr-2" /> Submit to Official Portal
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}

        {/* STEP 3: Successful Automation & Official Payment Trigger */}
        {step === 3 && filingResult && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Card gradient glow className="p-8 text-center space-y-6">
              <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500 text-green-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-10 h-10" />
              </div>

              <div>
                <h2 className="text-2xl font-bold font-display text-white">Successfully Automated on Govt Portal!</h2>
                <p className="text-slate-300 text-sm mt-2 max-w-lg mx-auto leading-relaxed">
                  {filingResult.message || "Your application was automatically entered into the Gujarat State RTI Portal."}
                </p>
              </div>

              {filingResult.portal_registration_number && (
                <div className="bg-slate-900 p-4 rounded-xl border border-slate-700 inline-block">
                  <p className="text-slate-400 text-xs uppercase font-bold">Portal Registration Number</p>
                  <p className="text-xl font-mono text-green-400 font-bold mt-1">
                    {filingResult.portal_registration_number}
                  </p>
                </div>
              )}

              {filingResult.payment_url && (
                <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-blue-500/40 p-6 rounded-2xl max-w-md mx-auto shadow-xl">
                  <p className="text-white font-bold text-lg mb-1">Government Fee Required (₹10)</p>
                  <p className="text-slate-300 text-xs mb-5 leading-relaxed">
                    Click below to open the official state treasury gateway and complete your ₹10 payment.
                  </p>
                  <a href={filingResult.payment_url} target="_blank" rel="noopener noreferrer">
                    <Button variant="primary" size="lg" className="w-full shadow-lg shadow-blue-500/20" glow>
                      Complete ₹10 Payment on Govt Portal <ExternalLink className="w-4 h-4 ml-2" />
                    </Button>
                  </a>
                </div>
              )}

              <div className="pt-4 flex justify-center gap-4">
                <Button variant="outline" onClick={() => router.push("/dashboard")}>
                  Go to Dashboard
                </Button>
                {draft && (
                  <Button variant="primary" onClick={() => router.push(`/track/${draft.tracking_number}`)}>
                    Track Application Status
                  </Button>
                )}
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}