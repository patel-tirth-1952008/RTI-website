"use client";
import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Clock, Building2, ShieldCheck, AlertCircle, CreditCard, KeyRound, FileText } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusTimeline } from "@/components/rti/status-timeline";
import { rtiAPI, filingAPI } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";

export default function TrackClient() {
  const params = useParams();
  const router = useRouter();
  const trackingNumber = (params?.id as string) || "";

  const [app, setApp] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [regInput, setRegInput] = useState("");
  const [showRegModal, setShowRegModal] = useState(false);
  const [showText, setShowText] = useState(false);

  useEffect(() => {
    if (trackingNumber) {
      fetchStatus();
    }
  }, [trackingNumber]);

  const fetchStatus = async () => {
    try {
      const res = await rtiAPI.getStatus(trackingNumber);
      setApp(res.data);
    } catch (err) {
      toast.error("Application not found.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRegNumber = async () => {
    if (!regInput.trim()) {
      toast.error("Please enter a valid Registration Number.");
      return;
    }
    try {
      await filingAPI.updateRegistration(trackingNumber, regInput.trim());
      toast.success("Government Registration Number linked!");
      setShowRegModal(false);
      fetchStatus();
    } catch (err) {
      toast.error("Failed to update registration number.");
    }
  };

  const handlePortalRefresh = async () => {
    if (!app?.portal_reference_number) {
      toast.error("Cannot check live status without a valid Government Registration Number.");
      return;
    }
    setChecking(true);
    try {
      const res = await filingAPI.checkPortalStatus(trackingNumber);
      toast.success(res.data.message || "Status updated from portal.");
      fetchStatus();
    } catch (err) {
      toast.error("Could not fetch live portal status at this time.");
    } finally {
      setChecking(false);
    }
  };

  if (loading) {
    return <div className="text-center py-20 text-slate-500">Loading tracking details...</div>;
  }

  if (!app) {
    return (
      <div className="text-center py-20">
        <p className="text-white font-bold">RTI Not Found</p>
        <Button variant="outline" className="mt-4" onClick={() => router.push("/dashboard")}>
          Return to Dashboard
        </Button>
      </div>
    );
  }

  const isOfficiallyFiled = !!app.portal_reference_number || app.status === "filed_successfully";

  const timelineSteps = [
    {
      label: "Application Drafted & Structured",
      status: "completed" as const,
      date: formatDate(app.created_at),
      description: "AI structured legal inquiries and formatted the RTI request.",
    },
    {
      label: "Portal Form Submission & Fee Payment",
      status: isOfficiallyFiled ? ("completed" as const) : ("current" as const),
      date: app.filing_date ? formatDate(app.filing_date) : undefined,
      description: app.portal_reference_number
        ? `Official Reg No: ${app.portal_reference_number}`
        : "Pending ₹10 fee receipt or official registration number.",
    },
    {
      label: "Statutory 30-Day PIO Response Period",
      status:
        app.status === "response_received"
          ? ("completed" as const)
          : isOfficiallyFiled
          ? ("current" as const)
          : ("upcoming" as const),
      date: app.response_due_date ? `Due: ${formatDate(app.response_due_date)}` : undefined,
      description: isOfficiallyFiled
        ? "Officer legally obligated to respond under Section 7(1) RTI Act."
        : "Clock starts once ₹10 fee is received by the government.",
    },
    {
      label: "Information Disclosed / Response Received",
      status: app.status === "response_received" ? ("completed" as const) : ("upcoming" as const),
      date: app.response_received_date ? formatDate(app.response_received_date) : undefined,
      description: app.response_summary || "Certified copies and official response.",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Button variant="ghost" size="sm" onClick={() => router.push("/dashboard")} className="mb-6">
        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Dashboard
      </Button>

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <span className="text-xs font-mono text-slate-500 uppercase tracking-wider">Internal Tracking Reference</span>
          <h1 className="text-2xl font-bold font-mono text-white">{app.tracking_number}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setShowText(!showText)}>
            <FileText className="w-4 h-4 mr-1.5" /> {showText ? "Hide Text" : "Inspect RTI Text"}
          </Button>
          {isOfficiallyFiled && (
            <Button variant="outline" size="sm" onClick={handlePortalRefresh} loading={checking}>
              <RefreshCw className="w-4 h-4 mr-2" /> Check Live Govt Portal
            </Button>
          )}
        </div>
      </div>

      {showText && (
        <Card gradient className="p-6 mb-8 border-blue-500/30">
          <h3 className="text-white font-bold text-sm mb-2 font-mono">Full Generated Application Text:</h3>
          <pre className="whitespace-pre-wrap text-xs font-mono text-slate-300 bg-slate-950 p-4 rounded-xl max-h-80 overflow-y-auto leading-relaxed border border-slate-800">
            {app.generated_body}
          </pre>
        </Card>
      )}

      {!isOfficiallyFiled && (
        <Card gradient className="p-6 mb-8 border-yellow-500/30 bg-yellow-500/5">
          <div className="flex items-start gap-4">
            <AlertCircle className="w-6 h-6 text-yellow-400 shrink-0 mt-0.5" />
            <div className="space-y-3">
              <h3 className="text-white font-bold text-base">Filing Not Complete (Fee Pending)</h3>
              <p className="text-slate-300 text-sm leading-relaxed">
                Under the RTI Act 2005, the 30-day clock only starts after the ₹10 fee is received by the government.
                If you already received a registration number in your email from the portal, enter it below.
              </p>
              <div className="flex flex-wrap gap-3 pt-2">
                <a href="https://rtionline.gov.in/request/request.php" target="_blank" rel="noreferrer">
                  <Button variant="primary" size="sm" glow>
                    <CreditCard className="w-4 h-4 mr-1.5" /> Complete ₹10 Fee
                  </Button>
                </a>
                <Button variant="outline" size="sm" onClick={() => setShowRegModal(!showRegModal)}>
                  <KeyRound className="w-4 h-4 mr-1.5" /> Link Govt Registration No.
                </Button>
              </div>

              {showRegModal && (
                <div className="flex items-center gap-2 pt-3">
                  <input
                    type="text"
                    placeholder="e.g. MOIAF/R/E/2026/12345 or GUJ/AMC/..."
                    value={regInput}
                    onChange={(e) => setRegInput(e.target.value)}
                    className="bg-slate-950 border border-blue-500 rounded-xl px-4 py-2 text-sm text-white w-full max-w-sm"
                  />
                  <Button size="sm" variant="primary" onClick={handleSaveRegNumber}>
                    Save Number
                  </Button>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card gradient className="p-5">
          <div className="flex items-center gap-3">
            <Building2 className="w-5 h-5 text-blue-400" />
            <div>
              <p className="text-slate-500 text-xs">Department</p>
              <p className="text-white text-sm font-semibold">{app.department_name || "Municipal Corp"}</p>
            </div>
          </div>
        </Card>

        <Card gradient className="p-5">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-5 h-5 text-green-400" />
            <div>
              <p className="text-slate-500 text-xs">Govt Registration No.</p>
              <p className="text-green-400 text-sm font-mono font-bold">
                {app.portal_reference_number || "Awaiting Fee Payment"}
              </p>
            </div>
          </div>
        </Card>

        <Card gradient className="p-5">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-orange-400" />
            <div>
              <p className="text-slate-500 text-xs">Statutory Response Clock</p>
              <p className="text-orange-400 text-sm font-bold">
                {isOfficiallyFiled
                  ? `${app.days_remaining ?? 30} Days Remaining`
                  : "Clock Paused (Unpaid)"}
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Card gradient className="p-8">
        <h2 className="text-lg font-bold text-white mb-6">Progress Lifecycle</h2>
        <StatusTimeline steps={timelineSteps} />
      </Card>
    </div>
  );
}