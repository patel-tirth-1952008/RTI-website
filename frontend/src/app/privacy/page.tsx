import React from "react";
import { Card } from "@/components/ui/card";

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 text-slate-300 space-y-6">
      <Card gradient className="p-8 space-y-6">
        <h1 className="text-3xl font-bold font-display text-white">Privacy Policy</h1>
        <p className="text-xs text-slate-500">Last Updated: September 2024</p>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">1. Information We Collect</h2>
          <p className="text-sm leading-relaxed">
            To generate and assist with Right to Information (RTI) applications under the RTI Act 2005,
            we collect user-provided details including name, postal address, email, phone number, and issue descriptions.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">2. Data Encryption & Security</h2>
          <p className="text-sm leading-relaxed">
            Personally Identifiable Information (PII) such as full name and home address is encrypted at rest
            using AES-128 cryptographic encryption before storage in our database. We do not store payment card,
            net banking, or UPI credentials.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">3. Third-Party Services</h2>
          <p className="text-sm leading-relaxed">
            User-submitted descriptions and images are processed via Google Gemini AI solely for issue categorisation
            and drafting questions. Data transmitted to government portals (`.gov.in` / `.nic.in`) is used strictly
            for processing your RTI request.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">4. Your Data Rights</h2>
          <p className="text-sm leading-relaxed">
            You may request deletion of your account and associated RTI draft records at any time directly through your dashboard.
          </p>
        </section>
      </Card>
    </div>
  );
}