import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: true
  },
  transpilePackages: ['three'],
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com"
      }
    ]
  }
};

const sentryBuildOptions = {
  // Suppresses source map upload logs during build; only runs when
  // SENTRY_AUTH_TOKEN + SENTRY_ORG + SENTRY_PROJECT are set.
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  // Do not attempt source map upload when auth token is missing (local dev).
  disableSourceMapUpload: !process.env.SENTRY_AUTH_TOKEN,
  widenClientFileUpload: true,
  tunnelRoute: "/monitoring",
  hideSourceMaps: true,
  disableLogger: true,
  automaticVercelMonitors: false,
};

export default withSentryConfig(nextConfig, sentryBuildOptions);
