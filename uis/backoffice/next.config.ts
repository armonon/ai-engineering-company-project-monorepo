import path from "node:path";
import type { NextConfig } from "next";

const apiOrigin = (
  process.env.TRACKFLOW_API_INTERNAL_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const talentApiOrigin = (
  process.env.TALENT_API_INTERNAL_URL ??
  "https://playground.4geeks.com/tracker/api/v1"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: path.resolve(__dirname, "../.."),
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
