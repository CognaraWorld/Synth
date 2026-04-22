"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/dashboard";
  const errorParam = params.get("error");

  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(
    errorParam ? "Sign-in failed. Check your email and try again." : null
  );

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const result = await signIn("dev-email", {
      email: email.trim(),
      redirect: false,
      callbackUrl
    });

    if (result?.error || !result?.ok) {
      setError("Couldn't sign in with that email. Make sure it's a valid address.");
      setSubmitting(false);
      return;
    }

    // On first sign-in a new user has no bot profile — send them through
    // onboarding. Existing users go straight to the dashboard (or wherever
    // the caller asked).
    try {
      const profileRes = await fetch("/api/bot-profile", { cache: "no-store" });
      if (profileRes.status === 404 || profileRes.status === 401) {
        router.replace("/onboarding");
        return;
      }
    } catch {
      // Fall through to callbackUrl if profile probe fails — the dashboard
      // will surface its own errors if needed.
    }

    // Destination comes from user input / NextAuth callback — not a static
    // route known to Next's typedRoutes generator, so cast is required.
    router.replace((result.url ?? callbackUrl) as Parameters<typeof router.replace>[0]);
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center space-y-3">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-primary text-primary-foreground shadow-glow">
            <Sparkles className="h-8 w-8" />
          </div>
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">Synth</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Enter your email to continue. First-time users get a new account automatically.
            </p>
          </div>
        </div>

        <Card>
          <CardContent className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@example.com"
                  autoFocus
                  autoComplete="email"
                  required
                />
              </div>

              {error ? (
                <p className="text-sm text-destructive" role="alert">
                  {error}
                </p>
              ) : null}

              <Button type="submit" className="w-full" disabled={submitting || !email.includes("@")}>
                {submitting ? "Signing in..." : "Continue"}
              </Button>
            </form>

            <p className="mt-4 text-center text-xs text-muted-foreground">
              Local dev uses email-only auth. Password and OAuth sign-in require additional setup.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInForm />
    </Suspense>
  );
}
