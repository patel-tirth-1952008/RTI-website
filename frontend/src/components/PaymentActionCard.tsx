"use client";

import React, { useState } from "react";
import { ExternalLink, CheckCircle2, AlertCircle, Loader2, ShieldCheck, CreditCard } from "lucide-react";

interface RTIProps {
  id: string;
  departmentName: string;
  state: string;
  status: string;
  paymentUrl?: string;
  govtRegNo?: string;
  createdAt: string;
}

export default function PaymentActionCard({ rti }: { rti: RTIProps }) {
  const [loading, setLoading] = useState(false);
  const [paymentUrl, setPaymentUrl] = useState<string | null>(rti.paymentUrl || null);
  const [regNo, setRegNo] = useState<string | null>(rti.govtRegNo || null);

  const handleStartAutoFiling = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/rti/auto-file-state-portal/${rti.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      const result = await response.json();
      if (result.status === "success") {
        setPaymentUrl(result.data.payment_url);
        if (result.data.registration_no) {
          setRegNo(result.data.registration_no);
        }
      }
    } catch (err) {
      console.error("Auto-filing error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-white shadow-xl">
      <div className="flex justify-between items-start mb-4">
        <div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20 mb-2 inline-block">
            {rti.state} Portal Automation
          </span>
          <h3 className="text-lg font-bold text-slate-100">{rti.departmentName}</h3>
          <p className="text-xs text-slate-400 mt-1">Created: {rti.createdAt}</p>
        </div>

        <div className="text-right">
          <span className="text-xs font-mono text-slate-400">Status</span>
          <p className="text-sm font-semibold text-emerald-400 flex items-center gap-1 justify-end">
            <ShieldCheck className="w-4 h-4" /> {rti.status.replace("_", " ")}
          </p>
        </div>
      </div>

      <div className="border-t border-slate-800 pt-4 mt-2">
        {paymentUrl ? (
          <div className="bg-emerald-950/30 border border-emerald-500/30 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-3">
              <CheckCircle2 className="w-6 h-6 text-emerald-400 flex-shrink-0" />
              <div>
                <h4 className="text-sm font-semibold text-emerald-300">Application Drafted & Prepared on State Portal</h4>
                <p className="text-xs text-slate-300 mt-0.5">
                  Your RTI details and attachments have been auto-filled. Complete the ₹10 statutory fee payment directly on the government portal.
                </p>
              </div>
            </div>

            <a
              href={paymentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-sm py-3 px-4 rounded-lg shadow-lg transition-all"
            >
              <CreditCard className="w-4 h-4" />
              Pay ₹10 Official Government Fee
              <ExternalLink className="w-4 h-4 ml-1" />
            </a>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-800/50 p-4 rounded-lg border border-slate-700">
            <div className="text-xs text-slate-300">
              <p className="font-medium text-slate-200">Ready for State Portal Filing</p>
              <p className="text-slate-400 mt-0.5">The agent will navigate to {rti.state} Portal, auto-login/register, and generate your payment link.</p>
            </div>

            <button
              onClick={handleStartAutoFiling}
              disabled={loading}
              className="w-full sm:w-auto flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs py-2.5 px-4 rounded-lg transition-all disabled:opacity-50 whitespace-nowrap"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Filing on State Portal...
                </>
              ) : (
                <>
                  Launch Agent & File RTI
                  <ExternalLink className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}

        {regNo && (
          <div className="mt-3 text-xs bg-slate-800 p-2.5 rounded border border-slate-700 text-slate-300 flex justify-between items-center">
            <span>Govt Registration Number:</span>
            <span className="font-mono font-bold text-amber-400">{regNo}</span>
          </div>
        )}
      </div>
    </div>
  );
}