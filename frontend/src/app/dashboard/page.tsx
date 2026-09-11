"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  PlusCircle, Clock, CheckCircle2, FileText, Search,
  ExternalLink, AlertCircle, CreditCard, KeyRound, Trash2, Eye, X, RefreshCw
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { rtiAPI, filingAPI } from "@/lib/api";
import { RTIApplication } from "@/types";
import { formatDate, getStatusColor, getStatusLabel, getCategoryIcon } from "@/lib/utils";
import toast from "react-hot-toast";

export default function DashboardPage() {
  const [applications, setApplications] = useState<RTIApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [updatingReg, setUpdatingReg] = useState<string | null>(null);
  const [regInput, setRegInput] = useState("");
  const [previewApp, setPreviewApp] = useState<any | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  useEffect(() => {
    fetchApplications();
  }, []);

  const fetchApplications = async () => {
    try {
      const res = await rtiAPI.list();
      setApplications(res.data.applications || []);
    } catch (err) {
      console.error("Failed to load applications", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDraft = async (trackingNumber: string) => {
    if (!confirm("Are you sure you want to delete this draft/attempt?")) return;
    try {
      await rtiAPI.delete(trackingNumber);
      toast.success("Application deleted.");
      fetchApplications();
    } catch (err) {
      toast.error("Failed to delete application.");
    }
  };

  const handleSaveRegNumber = async (trackingNumber: string) => {
    if (!regInput.trim()) {
      toast.error("Please enter the registration number.");
      return;
    }
    try {
      await filingAPI.updateRegistration(trackingNumber, regInput.trim());
      toast.success("Official Registration Number linked!");
      setUpdatingReg(null);
      setRegInput("");
      fetchApplications();
    } catch (err) {
      toast.error("Failed to update registration number.");
    }
  };

  const handleRetryFiling = async (trackingNumber: string) => {
    setRetrying(trackingNumber);
    try {
      const res = await filingAPI.submit({
        tracking_number: trackingNumber,
        gender: "male",
        education: "graduate",
        area_type: "urban",
        consent_to_file: true,
      });

      if (res.data.payment_url) {
        toast.success("Portal active! Redirecting to official payment page...");
        window.open(res.data.payment_url, "_blank");
      } else if (res.data.portal_registration_number) {
        toast.success(`Filed successfully! Reg No: ${res.data.portal_registration_number}`);
      } else {
        toast.success(res.data.message || "Form submitted on portal.");
      }
      fetchApplications();
    } catch (err: any) {
      toast.error(err.response?.data?.detail?.message || "Govt portal still unresponsive. Try again shortly.");
    } finally {
      setRetrying(null);
    }
  };

  const filtered = applications.filter(
    (app) =>
      app.tracking_number.toLowerCase().includes(search.toLowerCase()) ||
      (app.department_name && app.department_name.toLowerCase().includes(search.toLowerCase())) ||
      (app.category && app.category.toLowerCase().includes(search.toLowerCase()))
  );

  const filedRTIs = filtered.filter(
    (a) => a.status === "filed_successfully" || a.status === "response_received" || !!a.portal_reference_number
  );
  const pendingActionRTIs = filtered.filter(
    (a) => a.status !== "filed_successfully" && a.status !== "response_received" && !a.portal_reference_number
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold font-display text-white">Citizen Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">Manage and track your official RTI filings</p>
        </div>
        <Link href="/new-rti">
          <Button variant="primary" glow>
            <PlusCircle className="w-5 h-5 mr-2" /> File New RTI
          </Button>
        </Link>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <Card gradient className="p-6">
          <p className="text-slate-400 text-xs uppercase font-bold tracking-wider">Officially Filed RTIs</p>
          <p className="text-3xl font-bold text-green-400 mt-1">{filedRTIs.length}</p>
        </Card>
        <Card gradient className="p-6">
          <p className="text-slate-400 text-xs uppercase font-bold tracking-wider">Pending Action / Drafts</p>
          <p className="text-3xl font-bold text-yellow-400 mt-1">{pendingActionRTIs.length}</p>
        </Card>
        <Card gradient className="p-6">
          <p className="text-slate-400 text-xs uppercase font-bold tracking-wider">Govt Responses</p>
          <p className="text-3xl font-bold text-blue-400 mt-1">
            {applications.filter((a) => a.status === "response_received").length}
          </p>
        </Card>
      </div>

      {/* Search */}
      <div className="relative mb-8">
        <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search by tracking number, department, or issue type..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-slate-900/60 border border-slate-700/80 rounded-xl pl-12 pr-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-500">Loading dashboard...</div>
      ) : applications.length === 0 ? (
        <Card gradient className="text-center py-16">
          <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-white font-semibold text-lg">No RTI Applications Found</p>
          <p className="text-slate-400 text-sm mt-1 mb-6">Upload a photo to generate and file your first RTI.</p>
          <Link href="/new-rti">
            <Button variant="primary" glow>File Your First RTI</Button>
          </Link>
        </Card>
      ) : (
        <div className="space-y-10">
          {/* SECTION 1: Officially Filed RTIs */}
          <div>
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              Officially Filed RTIs ({filedRTIs.length})
            </h2>
            {filedRTIs.length === 0 ? (
              <p className="text-slate-500 text-sm bg-slate-900/40 p-4 rounded-xl border border-slate-800">
                No active RTIs with verified fee payment or registration numbers yet.
              </p>
            ) : (
              <div className="space-y-4">
                {filedRTIs.map((app) => (
                  <Card key={app.tracking_number} gradient className="p-6">
                    <div className="flex flex-col md:flex-row justify-between md:items-center gap-4">
                      <div className="flex items-start gap-4">
                        <span className="text-3xl p-3 bg-slate-900 rounded-xl border border-slate-700">
                          {getCategoryIcon(app.category)}
                        </span>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-sm font-bold text-white">{app.tracking_number}</span>
                            <Badge variant="success">Govt Reg: {app.portal_reference_number}</Badge>
                          </div>
                          <p className="text-slate-300 font-medium text-sm mt-1">
                            {app.department_name || "Department Processing"}
                          </p>
                          <p className="text-slate-500 text-xs mt-1">Filed: {formatDate(app.filing_date || app.created_at)}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <Button variant="ghost" size="sm" onClick={() => setPreviewApp(app)}>
                          <Eye className="w-4 h-4 mr-1" /> View Text
                        </Button>
                        <Link href={`/track/${app.tracking_number}`}>
                          <Button variant="outline" size="sm">
                            Track Live <ExternalLink className="w-3.5 h-3.5 ml-1" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* SECTION 2: Drafts & Pending Actions */}
          <div>
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-yellow-400" />
              Pending Payment / Unfinished Drafts ({pendingActionRTIs.length})
            </h2>
            {pendingActionRTIs.length === 0 ? (
              <p className="text-slate-500 text-sm bg-slate-900/40 p-4 rounded-xl border border-slate-800">
                No pending drafts.
              </p>
            ) : (
              <div className="space-y-4">
                {pendingActionRTIs.map((app) => (
                  <Card key={app.tracking_number} gradient className="p-6 border-yellow-500/20">
                    <div className="flex flex-col md:flex-row justify-between md:items-center gap-4">
                      <div className="flex items-start gap-4">
                        <span className="text-3xl p-3 bg-slate-900 rounded-xl border border-slate-700">
                          {getCategoryIcon(app.category)}
                        </span>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-sm font-bold text-slate-300">{app.tracking_number}</span>
                            <Badge variant="warning">Incomplete / Unpaid</Badge>
                          </div>
                          <p className="text-slate-300 font-medium text-sm mt-1">
                            {app.department_name || "Department Selected"}
                          </p>
                          <p className="text-slate-500 text-xs mt-1">Created: {formatDate(app.created_at)}</p>
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setPreviewApp(app)}>
                          <Eye className="w-3.5 h-3.5 mr-1" /> Inspect RTI
                        </Button>

                        <Button
                          variant="primary"
                          size="sm"
                          glow
                          loading={retrying === app.tracking_number}
                          onClick={() => handleRetryFiling(app.tracking_number)}
                        >
                          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Retry Auto-Filing
                        </Button>

                        {updatingReg === app.tracking_number ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              placeholder="Paste Reg No"
                              value={regInput}
                              onChange={(e) => setRegInput(e.target.value)}
                              className="bg-slate-950 border border-blue-500 rounded-lg px-3 py-1.5 text-xs text-white"
                            />
                            <Button size="sm" variant="primary" onClick={() => handleSaveRegNumber(app.tracking_number)}>
                              Save
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setUpdatingReg(null)}>
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <Button variant="outline" size="sm" onClick={() => setUpdatingReg(app.tracking_number)}>
                            <KeyRound className="w-3.5 h-3.5 mr-1" /> Link Reg No
                          </Button>
                        )}

                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDeleteDraft(app.tracking_number)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* INSPECT DRAFT MODAL */}
      {previewApp && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-xs font-mono text-blue-400">{previewApp.tracking_number}</span>
                <h3 className="text-white font-bold text-lg">Application Content Inspection</h3>
              </div>
              <button onClick={() => setPreviewApp(null)} className="text-slate-400 hover:text-white p-1">
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs text-slate-300 bg-slate-950 p-4 rounded-xl border border-slate-800">
              <p><strong>Department:</strong> {previewApp.department_name}</p>
              <p><strong>Location:</strong> {previewApp.issue_location}</p>
              <p><strong>Status:</strong> {previewApp.status}</p>
              <div className="pt-2 border-t border-slate-800">
                <p className="font-bold text-blue-300 mb-2">Subject:</p>
                <p>{previewApp.generated_subject}</p>
              </div>
              <div className="pt-2 border-t border-slate-800">
                <p className="font-bold text-blue-300 mb-2">Full Application Body:</p>
                <pre className="whitespace-pre-wrap leading-relaxed">{previewApp.generated_body}</pre>
              </div>
            </div>

            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setPreviewApp(null)}>
                Close Preview
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}