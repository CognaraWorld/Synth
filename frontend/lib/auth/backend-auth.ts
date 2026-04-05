import "server-only";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function exchangeForBackendToken(email: string, name: string): Promise<string | null> {
  const serviceSecret = process.env.BACKEND_SERVICE_SECRET;
  if (!serviceSecret || !email) return null;

  try {
    const response = await fetch(`${BACKEND_URL}/api/auth/service-token`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        name: name || "User",
        service_secret: serviceSecret
      })
    });

    if (!response.ok) {
      return null;
    }

    const data = (await response.json().catch(() => null)) as { access_token?: string } | null;
    return data?.access_token ?? null;
  } catch {
    return null;
  }
}
