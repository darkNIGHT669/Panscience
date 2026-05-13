/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: { serverActions: { allowedOrigins: ["localhost"] } },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://backend:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
