"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { createAgent } from "@/lib/api";

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<"general" | "custom">("general");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await createAgent({ name: name.trim(), description: description.trim(), mode });
      router.push("/dashboard/agents");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to create agent. Please try again.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const isFormValid = name.trim().length > 0 && description.trim().length > 0;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="mb-4 gap-1.5"
          render={<Link href="/dashboard/agents" />}
        >
          <ArrowLeft className="size-3.5" />
          Back to Agents
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">Create New Agent</h1>
        <p className="text-sm text-muted-foreground">
          Configure an agent to join your meetings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Details</CardTitle>
          <CardDescription>
            Set up the name, description, and behavior mode for your agent.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="name">Agent Name</Label>
              <Input
                id="name"
                placeholder="e.g. Meeting Note Taker"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={submitting}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Describe what this agent should focus on during meetings..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={submitting}
                rows={3}
              />
            </div>

            <div className="space-y-3">
              <Label>Mode</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setMode("general")}
                  disabled={submitting}
                  className={`flex flex-col gap-1 rounded-lg border p-4 text-left transition-colors ${
                    mode === "general"
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-muted-foreground/25"
                  }`}
                >
                  <span className="text-sm font-medium">General</span>
                  <span className="text-xs text-muted-foreground">
                    Works across all meeting types with balanced defaults.
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setMode("custom")}
                  disabled={submitting}
                  className={`flex flex-col gap-1 rounded-lg border p-4 text-left transition-colors ${
                    mode === "custom"
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-muted-foreground/25"
                  }`}
                >
                  <span className="text-sm font-medium">Custom</span>
                  <span className="text-xs text-muted-foreground">
                    Fine-tuned with your documents and specific instructions.
                  </span>
                </button>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={!isFormValid || submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" data-icon="inline-start" />
                    Creating...
                  </>
                ) : (
                  "Create Agent"
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={submitting}
                render={<Link href="/dashboard/agents" />}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
