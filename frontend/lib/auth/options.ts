import { PrismaAdapter } from "@next-auth/prisma-adapter";
import type { NextAuthOptions } from "next-auth";
import EmailProvider from "next-auth/providers/email";
import GoogleProvider from "next-auth/providers/google";
import { exchangeForBackendToken } from "@/lib/auth/backend-auth";
import { prisma } from "@/lib/prisma";

const providers = [];

if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET
    })
  );
}

if (
  process.env.EMAIL_SERVER_HOST &&
  process.env.EMAIL_SERVER_USER &&
  process.env.EMAIL_SERVER_PASSWORD &&
  process.env.EMAIL_FROM
) {
  providers.push(
    EmailProvider({
      server: {
        host: process.env.EMAIL_SERVER_HOST,
        port: Number(process.env.EMAIL_SERVER_PORT ?? 587),
        auth: {
          user: process.env.EMAIL_SERVER_USER,
          pass: process.env.EMAIL_SERVER_PASSWORD
        }
      },
      from: process.env.EMAIL_FROM
    })
  );
}

// In-memory cache for backend JWT tokens (keyed by user email).
// Tokens last 24h on the backend; we cache for 1h to avoid hitting
// the service-token endpoint on every getServerSession() call.
const TOKEN_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour
const tokenCache = new Map<string, { token: string; expiresAt: number }>();

async function getCachedBackendToken(email: string, name: string): Promise<string | null> {
  const cached = tokenCache.get(email);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.token;
  }

  const token = await exchangeForBackendToken(email, name);
  if (token) {
    tokenCache.set(email, { token, expiresAt: Date.now() + TOKEN_CACHE_TTL_MS });
  }
  return token;
}

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma),
  providers,
  session: {
    strategy: "database"
  },
  pages: {
    signIn: "/onboarding"
  },
  callbacks: {
    session: async ({ session, user }) => {
      if (session.user) {
        session.user.id = user.id;
      }

      const token = await getCachedBackendToken(user.email ?? "", user.name ?? "");
      if (token) {
        session.backendToken = token;
      }

      return session;
    }
  }
};
