import React from "react";
import Link from "next/link";
import { Shield } from "lucide-react";

export function Footer() {
  return (
    <footer
      style={{
        borderTop: "1px solid #1e293b",
        background: "rgba(2, 6, 23, 0.9)",
      }}
    >
      <div className="max-w-7xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{
                  background: "linear-gradient(135deg, #FF9933, #fff, #138808)",
                }}
              >
                <Shield className="w-4 h-4" style={{ color: "#000080" }} />
              </div>
              <span className="text-lg font-bold text-white">RTI Sarthi</span>
            </div>
            <p className="text-slate-400 text-sm max-w-md leading-relaxed">
              Empowering Indian citizens to exercise their Right to Information.
              Upload a photo, let AI draft your application, and file it
              directly with government portals — all for free.
            </p>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-3">Resources</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <a
                  href="https://rtionline.gov.in"
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-blue-400 transition-colors"
                >
                  Central RTI Portal
                </a>
              </li>
              <li>
                <a
                  href="https://rti.gujarat.gov.in"
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-blue-400 transition-colors"
                >
                  Gujarat RTI Portal
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="text-white font-semibold mb-3">Legal & Compliance</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link href="/privacy" className="hover:text-blue-400 transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-blue-400 transition-colors">
                  Terms of Service
                </Link>
              </li>
              <li>
                <Link href="/disclaimer" className="hover:text-blue-400 transition-colors">
                  Government Disclaimer
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div
          className="mt-8 pt-8 flex flex-col md:flex-row justify-between items-center gap-4"
          style={{ borderTop: "1px solid #1e293b" }}
        >
          <p className="text-sm text-slate-500">
            © {new Date().getFullYear()} RTI Sarthi. All Rights Reserved. Proprietary software & workflow design.
          </p>
          <p className="text-xs text-slate-600">
            Unauthorized copying, reverse-engineering, or reproduction of platform workflows is strictly prohibited.
          </p>
        </div>
      </div>
    </footer>
  );
}