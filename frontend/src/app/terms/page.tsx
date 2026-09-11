import React from "react";
import { Card } from "@/components/ui/card";

export default function TermsOfServicePage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 text-slate-300 space-y-6">
      <Card gradient className="p-8 space-y-6">
        <h1 className="text-3xl font-bold font-display text-white">Terms of Service</h1>
        <p className="text-xs text-slate-500">Last Updated: September 2024</p>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">1. Platform Purpose</h2>
          <p className="text-sm leading-relaxed">
            RTI Sarthi is an independent technology platform designed to assist Indian citizens in drafting and filing
            applications under the Right to Information Act, 2005.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">2. Acceptable Usage</h2>
          <p className="text-sm leading-relaxed">
            Users agree to submit true, accurate, and genuine public interest inquiries. Submitting fraudulent identities,
            harassing content, or abusive requests is strictly prohibited.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">3. Statutory Fee Responsibility</h2>
          <p className="text-sm leading-relaxed">
            Application fees (e.g., ₹10 standard statutory fee) are paid directly by the user to official government accounts
            via designated government payment gateways. RTI Sarthi does not collect or retain statutory government fees.
          </p>
        </section>
      </Card>
    </div>
  );
}