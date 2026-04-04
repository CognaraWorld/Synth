"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Bot, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { AgentsPageSkeleton } from "@/components/dashboard/loading-skeleton";
import { getAgents } from "@/lib/api";
import api from "@/lib/api";

interface Agent {
  id: string;
  name: string;
  description: string;
  mode: "general" | "custom";
  created_at?: string;
  createdAt?: string;
}

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
      <Button nativeButton={false} render={<Link href="/dashboard/agents/new" />}>
        <Plus className="size-4" data-icon="inline-start" />
        Create Agent
      </Button>
    </div>
  );
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null);

  useEffect(() => {
    fetchAgents();
  }, []);

  async function fetchAgents() {
    try {
      setError(null);
      const data = await getAgents();
      setAgents(Array.isArray(data) ? data : []);
    } catch (err) {
      setError("Failed to load agents. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!agentToDelete) return;
    setDeletingId(agentToDelete.id);
    try {
      await api.delete(`/agents/${agentToDelete.id}`);
      setAgents((prev) => prev.filter((a) => a.id !== agentToDelete.id));
      setDeleteDialogOpen(false);
      setAgentToDelete(null);
    } catch (err) {
      setError("Failed to delete agent. Please try again.");
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <AgentsPageSkeleton />;
  }

  if (error && agents.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Agents</h1>
          <p className="text-sm text-muted-foreground">
            Manage your meeting agents.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center gap-4 py-16">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchAgents(); }}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

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
          <Button nativeButton={false} render={<Link href="/dashboard/agents/new" />}>
            <Plus className="size-4" data-icon="inline-start" />
            Create New Agent
          </Button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {hasAgents ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Card key={agent.id} className="group relative">
              <Link
                href={`/dashboard/agents/${agent.id}`}
                className="absolute inset-0 z-0"
              >
                <span className="sr-only">View {agent.name}</span>
              </Link>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle>{agent.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        agent.mode === "custom" ? "default" : "secondary"
                      }
                    >
                      {agent.mode}
                    </Badge>
                    <Dialog
                      open={deleteDialogOpen && agentToDelete?.id === agent.id}
                      onOpenChange={(open) => {
                        setDeleteDialogOpen(open);
                        if (!open) setAgentToDelete(null);
                      }}
                    >
                      <DialogTrigger
                        render={
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            className="relative z-10 opacity-0 transition-opacity group-hover:opacity-100"
                            onClick={(e) => {
                              e.preventDefault();
                              setAgentToDelete(agent);
                              setDeleteDialogOpen(true);
                            }}
                          />
                        }
                      >
                        <Trash2 className="size-3.5 text-destructive" />
                        <span className="sr-only">Delete {agent.name}</span>
                      </DialogTrigger>
                      <DialogContent showCloseButton={false}>
                        <DialogHeader>
                          <DialogTitle>Delete Agent</DialogTitle>
                          <DialogDescription>
                            Are you sure you want to delete &ldquo;{agent.name}&rdquo;? This action cannot be undone.
                          </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                          <DialogClose
                            render={<Button variant="outline" />}
                          >
                            Cancel
                          </DialogClose>
                          <Button
                            variant="destructive"
                            onClick={handleDelete}
                            disabled={deletingId === agent.id}
                          >
                            {deletingId === agent.id ? (
                              <>
                                <Loader2 className="size-3.5 animate-spin" data-icon="inline-start" />
                                Deleting...
                              </>
                            ) : (
                              "Delete"
                            )}
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
                <CardDescription>{agent.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Created {agent.created_at || agent.createdAt || "recently"}
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
