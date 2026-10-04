const path = require("path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  serverExternalPackages: ["@resvg/resvg-js", "harfbuzzjs"],
  outputFileTracingIncludes: { "/story/[slug]/card": ["./src/assets/**"] }
};

module.exports = nextConfig;
