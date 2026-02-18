import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",          // static site → deploy anywhere (Vercel, GH Pages, etc.)
  images: { unoptimized: true },
};

export default nextConfig;
