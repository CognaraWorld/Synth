import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center px-4">
      <div className="absolute top-0 right-0 p-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/login">Sign In</Link>
        </Button>
      </div>
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-8 text-center">
        <div className="flex flex-col gap-4">
          <h1 className="text-5xl font-bold tracking-tight sm:text-6xl">
            Synth
          </h1>
          <p className="text-lg text-muted-foreground sm:text-xl">
            Your meeting participant. Joins calls, takes notes, and delivers
            actionable summaries — so you can stay present.
          </p>
        </div>
        <div className="flex gap-4">
          <Button size="lg" asChild>
            <Link href="/login">Get Started</Link>
          </Button>
          <Button variant="outline" size="lg" asChild>
            <Link href="/onboarding">Create Account</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
