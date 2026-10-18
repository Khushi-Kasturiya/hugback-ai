/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false, // Avoid double mounting audio contexts in dev
  output: "standalone",
};

export default nextConfig;
