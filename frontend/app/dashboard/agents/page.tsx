import Link from "next/link";
import { Plus, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const agents = [
  {
    id: "1",
    name: "Note Taker",
    description: "General-purpose meeting note taker with smart summaries.",
    mode: "general" as const,
    createdAt: "2026-03-15",
  },
  {
    id: "2",
    name: "Sales Call Analyst",
    description: "Tracks objections, action items, and follow-ups from sales calls.",
    mode: "custom" as const,
    createdAt: "2026-03-20",
  },
  {
    id: "3",
    name: "Standup Bot",
    description: "Records daily standup updates and flags blockers.",
    mode: "general" as const,
    createdAt: "2026-03-28",
  },
];

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border py-16">
      <div className="rounded-full bg-muted p-3">
        <Bot className="size-6 text-muted-foreground" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium">No agents yet</p>
        <p className="text-sm text-muted-foreground">
          Create your first agent to get started.
        </p>
      </div>
      <Button render={<Link href="/dashboard/agents/new" />}>
        <Plus className="size-4" data-icon="inline-start" />
        Create Agent
      </Button>
    </div>
  );
}

export default function AgentsPage() {
  const hasAgents = agents.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Agents</h1>
          <p className="text-sm text-muted-foreground">
            Manage your meeting agents.
          </p>
        </div>
        {hasAgents && (
          <Button render={<Link href="/dashboard/agents/new" />}>
            <Plus className="size-4" data-icon="inline-start" />
            Create New Agent
          </Button>
        )}
      </div>

      {hasAgents ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Card key={agent.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>{agent.name}</CardTitle>
                  <Badge
                    variant={agent.mode === "custom" ? "default" : "secondary"}
                  >
                    {agent.mode}
                  </Badge>
                </div>
                <CardDescription>{agent.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Created {agent.createdAt}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
