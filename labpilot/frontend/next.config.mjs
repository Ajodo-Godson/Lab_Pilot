import fs from "node:fs";
import path from "node:path";

const rootEnvPath = path.resolve(process.cwd(), "..", ".env");

if (fs.existsSync(rootEnvPath)) {
  const lines = fs.readFileSync(rootEnvPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...valueParts] = trimmed.split("=");
    if (!process.env[key]) {
      process.env[key] = valueParts.join("=").trim();
    }
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {};

export default nextConfig;
