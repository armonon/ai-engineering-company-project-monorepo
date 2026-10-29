import path from "node:path";
import type { NextConfig } from "next";

const allowedDevOrigins = [
  "127.0.0.1",
  "localhost",
  ...(process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean),
];

const apiOrigin = (
  process.env.TRACKFLOW_API_INTERNAL_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const talentApiOrigin = (
  process.env.TALENT_API_INTERNAL_URL ??
  "https://playground.4geeks.com/tracker/api/v1"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  allowedDevOrigins,
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
  async rewrites() {
    return [
      {
        source: "/trackflow-api/:path*",
        destination: `${apiOrigin}/:path*`,
      },
      {
        source: "/talent-api/:path*",
        destination: `${talentApiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
