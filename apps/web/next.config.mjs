import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // The browser always talks same-origin; the Next server proxies to the
  // FastAPI service natively. No browser-side localhost.
  async rewrites() {
    return [
      { source: "/api/health/:path*", destination: `${API_PROXY_TARGET}/health/:path*` },
      { source: "/api/docs", destination: `${API_PROXY_TARGET}/docs` },
      { source: "/api/openapi.json", destination: `${API_PROXY_TARGET}/openapi.json` },
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/:path*` },
    ];
  },
};

export default withNextIntl(nextConfig);
