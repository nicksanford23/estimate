import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow the Codespaces forwarded origin so Next dev's HMR/RSC requests
  // aren't blocked as cross-origin. Codespaces port forwarding carries the
  // HMR WebSocket (unlike the cloudflare quick tunnel), so dev-mode hot
  // reload works over this URL.
  allowedDevOrigins: [
    `${process.env.CODESPACE_NAME}-3311.app.github.dev`,
    "*.app.github.dev",
  ],
};

export default nextConfig;
