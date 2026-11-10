/** @type {import('next').NextConfig} */
// NEXT_PUBLIC_API_URL is read when the site is built. Change it in Vercel, then redeploy.
// Use the public https backend address. A private Railway hostname fails with
// DNS_HOSTNAME_RESOLVED_PRIVATE and every search looks broken.
const apiBase = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
