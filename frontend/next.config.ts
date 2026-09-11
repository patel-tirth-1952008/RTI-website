import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  // --- ENTERPRISE CONFIDENTIALITY & IP PROTECTIONS ---
  productionBrowserSourceMaps: false, // Prevents exposing raw React/TypeScript source code in DevTools
  compiler: {
    removeConsole: process.env.NODE_ENV === "production", // Strips all console.log statements in production
  },
  reactStrictMode: true,
  poweredByHeader: false, // Hides the "X-Powered-By: Next.js" header to conceal technology stack details
};

export default nextConfig;