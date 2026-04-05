"use client";

import { useState } from "react";
import { CreditCard, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const PACKS = [
  { packId: "pack_5", credits: 5, price: "$30" },
  { packId: "pack_20", credits: 20, price: "$100" },
  { packId: "pack_50", credits: 50, price: "$200" }
];

export function BuyCreditsSection() {
  const [activePack, setActivePack] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startCheckout(packId: string) {
    setActivePack(packId);
    setError(null);

    try {
      const response = await fetch("/api/payments/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pack_id: packId })
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null) as { error?: string } | null;
        throw new Error(body?.error || "Failed to start checkout");
      }

      const result = (await response.json()) as { data: { checkout_url: string } };
      if (result.data?.checkout_url) {
        window.location.assign(result.data.checkout_url);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed. Please try again.");
      setActivePack(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Buy Credits</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-3">
        {PACKS.map((pack) => (
          <div key={pack.packId} className="rounded-2xl border border-border/70 bg-background/60 p-5">
            <p className="text-sm text-muted-foreground">Credit pack</p>
            <p className="mt-2 text-2xl font-semibold">{pack.credits} credits</p>
            <p className="mt-1 text-sm text-muted-foreground">{pack.price} one-time purchase</p>
            <Button className="mt-5 w-full" onClick={() => startCheckout(pack.packId)} disabled={activePack === pack.packId}>
              {activePack === pack.packId ? <Loader2 className="h-4 w-4 animate-spin" /> : <CreditCard className="h-4 w-4" />}
              {activePack === pack.packId ? "Redirecting..." : "Buy now"}
            </Button>
          </div>
        ))}
        </div>
      </CardContent>
    </Card>
  );
}
