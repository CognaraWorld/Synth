import { PrismaAdapter } from "@next-auth/prisma-adapter";
import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
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

// Dev sign-in: email-only credentials. Upserts a Prisma user on first sign-in
// so local testing can proceed without external OAuth or SMTP setup. Never
// enable this path in production — set NODE_ENV=production to disable.
if (process.env.NODE_ENV !== "production") {
  providers.push(
    CredentialsProvider({
      id: "dev-email",
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email", placeholder: "you@example.com" }
      },
      async authorize(credentials) {
        const email = (credentials?.email ?? "").trim().toLowerCase();
        if (!email || !email.includes("@")) return null;

        const name = email.split("@")[0];
        const user = await prisma.user.upsert({
          where: { email },
          update: {},
          create: { email, name }
        });
        return { id: user.id, email: user.email, name: user.name ?? name };
      }
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

// Credentials provider requires JWT session strategy in NextAuth v4 —
// database sessions are incompatible with Credentials. JWT also removes
// a DB round-trip per session check, which is a nice side win.
export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma),
  providers,
  session: {
    strategy: "jwt"
  },
  pages: {
    signIn: "/signin"
  },
  callbacks: {
    jwt: async ({ token, user }) => {
      if (user) {
        token.id = user.id;
        token.email = user.email ?? undefined;
        token.name = user.name ?? undefined;
      }
      return token;
    },
    session: async ({ session, token }) => {
      if (session.user && token) {
        session.user.id = (token.id as string) ?? (token.sub as string) ?? "";
      }

      const email = session.user?.email ?? (token?.email as string | undefined) ?? "";
      const name = session.user?.name ?? (token?.name as string | undefined) ?? "";
      if (email) {
        const backendToken = await getCachedBackendToken(email, name);
        if (backendToken) {
          session.backendToken = backendToken;
        }
      }

      return session;
    }
  }
};
