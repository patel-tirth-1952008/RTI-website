import React from "react";
import { Card } from "@/components/ui/card";

export default function DisclaimerPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12 text-slate-300 space-y-6">
      <Card gradient className="p-8 space-y-6">
        <h1 className="text-3xl font-bold font-display text-white">Government Disclaimer</h1>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-white">Non-Affiliation Notice</h2>
          <p className="text-sm leading-relaxed">
            RTI Sarthi is an independent civic-tech platform and is <strong>NOT affiliated, associated, authorized, endorsed by, or in any way officially connected with</strong> the Government of India, any State Government, National Informatics Centre (NIC), or any Public Authority.
          </p>
          <p className="text-sm leading-relaxed">
            Official government RTI portals can be accessed directly at <a href="https://rtionline.gov.in" target="_blank" rel="noreferrer" className="text-blue-400 underline">rtionline.gov.in</a> and respective state government web portals.
          </p>
        </section>
      </Card>
    </div>
  );
}