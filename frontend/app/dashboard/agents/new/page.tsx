"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<"general" | "custom">("general");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Will integrate with API later
    console.log({ name, description, mode });
    router.push("/dashboard/agents");
  }

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
            <div className="space-y-2">
              <Label htmlFor="name">Agent Name</Label>
              <Input
                id="name"
                placeholder="e.g. Meeting Note Taker"
                value={name}
                onChange={(e) => setName(e.target.value)}
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
                rows={3}
              />
            </div>

            <div className="space-y-3">
              <Label>Mode</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setMode("general")}
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
              <Button type="submit" disabled={!name.trim()}>
                Create Agent
              </Button>
              <Button
                type="button"
                variant="outline"
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
