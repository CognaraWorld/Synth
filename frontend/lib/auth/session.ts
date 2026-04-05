import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth/options";

export async function getCurrentSession() {
  return getServerSession(authOptions);
}

export async function getCurrentUserId(): Promise<string | null> {
  const session = await getCurrentSession();
  return session?.user?.id ?? null;
}

export async function getBackendToken(): Promise<string | null> {
  const session = await getCurrentSession();
  return session?.backendToken ?? null;
}
