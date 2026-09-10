import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/layout/navbar";
import { Footer } from "@/components/layout/footer";
import { Toaster } from "react-hot-toast";

export const metadata: Metadata = {
  title: "RTI Sarthi — File RTI Online",
  description: "Upload a photo, let AI draft your RTI application, and file it directly with Indian government portals.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" data-scroll-behavior="smooth">
      <body className="min-h-screen flex flex-col antialiased bg-slate-950 text-slate-50">
        <Navbar />
        <main className="flex-1 pt-16">{children}</main>
        <Footer />
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "#1e293b",
              color: "#f1f5f9",
              border: "1px solid #334155",
              borderRadius: "12px",
            },
          }}
        />
      </body>
    </html>
  );
}