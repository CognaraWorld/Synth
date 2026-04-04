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
import { createAgent, type PersonaId } from "@/lib/api";

const PERSONA_OPTIONS: Array<{
  id: PersonaId;
  title: string;
  description: string;
  voice: "Female" | "Male";
}> = [
  {
    id: "general",
    title: "General",
    description: "Inclusive and balanced for mixed audiences.",
    voice: "Female",
  },
  {
    id: "strategist",
    title: "Strategist",
    description: "Decision-first with tradeoffs and next-step options.",
    voice: "Male",
  },
  {
    id: "analyst",
    title: "Analyst",
    description: "Evidence-driven, precise, and assumption-aware.",
    voice: "Female",
  },
  {
    id: "challenger",
    title: "Challenger",
    description: "Politely stress-tests ideas and surfaces blind spots.",
    voice: "Male",
  },
  {
    id: "facilitator",
    title: "Facilitator",
    description: "Keeps alignment, clarity, and participation moving.",
    voice: "Female",
  },
];

const PRESET_DEFAULT_DESCRIPTIONS: Record<PersonaId, string> = {
  general: "Inclusive, balanced meeting copilot for mixed audiences.",
  strategist: "Outcome-focused strategist who highlights decisions, tradeoffs, and next actions.",
  analyst: "Data-driven analyst who separates facts, assumptions, and conclusions clearly.",
  challenger: "Constructive challenger who surfaces risks, edge cases, and alternatives.",
  facilitator: "Facilitator who drives alignment, summarizes threads, and invites input across participants.",
};

export default function NewAgentPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [personaId, setPersonaId] = useState<PersonaId>("general");
  const [meetingContext, setMeetingContext] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const description =
        meetingContext.trim() || PRESET_DEFAULT_DESCRIPTIONS[personaId];

      await createAgent({
        name: name.trim(),
        description,
        mode: "general",
        persona_id: personaId,
      });
      router.push("/dashboard/agents");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to create agent. Please try again.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const isFormValid = name.trim().length > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="mb-4 gap-1.5"
          nativeButton={false}
          render={<Link href="/dashboard/agents" />}
        >
          <ArrowLeft className="size-3.5" />
          Back to Agents
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">Create New Agent</h1>
        <p className="text-sm text-muted-foreground">
          Pick one of the 5 fixed personas. Voice is auto-assigned per persona.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Details</CardTitle>
          <CardDescription>
            Persona behavior and voice are fixed for consistency and clearer differentiation.
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
                placeholder="e.g. Synth"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={submitting}
                required
              />
            </div>

            <div className="space-y-3">
              <Label>Persona</Label>
              <div className="grid gap-3 sm:grid-cols-2">
                {PERSONA_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setPersonaId(option.id)}
                    disabled={submitting}
                    className={`flex flex-col gap-1 rounded-lg border p-4 text-left transition-colors ${
                      personaId === option.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-muted-foreground/25"
                    }`}
                  >
                    <span className="text-sm font-medium">{option.title}</span>
                    <span className="text-xs text-muted-foreground">{option.description}</span>
                    <span className="pt-1 text-xs text-muted-foreground">Voice: {option.voice}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="meeting-context">Optional Context</Label>
              <Textarea
                id="meeting-context"
                placeholder="Add team/company context to tailor this persona further..."
                value={meetingContext}
                onChange={(e) => setMeetingContext(e.target.value)}
                disabled={submitting}
                rows={3}
              />
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
                nativeButton={false}
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
