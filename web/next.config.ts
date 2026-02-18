import type { NextConfig } from "next";
import { loadEnvConfig } from "@next/env";
import path from "path";

// Load env vars from root .env.local (single source of truth)
loadEnvConfig(path.resolve(__dirname, ".."));

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ['*'],
};

export default nextConfig;
