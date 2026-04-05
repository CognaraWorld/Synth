"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Video, Bot, CreditCard, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatsCard } from "@/components/dashboard/stats-card";
import { DashboardPageSkeleton } from "@/components/dashboard/loading-skeleton";
import { getAgents, getMeetings } from "@/lib/api";
import api from "@/lib/api";

interface UserInfo {
  id: string;
  email: string;
  name: string;
  credits: number;
}

interface Meeting {
  id: string;
  agent_id: string;
  platform: string;
  meeting_link: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number | null;
  created_at: string;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  mode: string;
}

export default function DashboardPage() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [userRes, agentsRes, meetingsRes] = await Promise.all([
          api.get("/auth/me"),
          getAgents(),
          getMeetings(),
        ]);
        setUser(userRes.data);
        setAgents(Array.isArray(agentsRes) ? agentsRes : []);
        setMeetings(Array.isArray(meetingsRes) ? meetingsRes : []);
      } catch (err) {
        setError("Failed to load dashboard data. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return <DashboardPageSkeleton />;
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  const recentMeetings = meetings.slice(0, 5);
  const totalMeetings = meetings.length;
  const activeAgents = agents.length;
  const credits = user?.credits ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Overview of your meetings and agents.
          </p>
        </div>
        <Button nativeButton={false} render={<Link href="/dashboard/agents/new" />}>
          <Plus className="size-4" data-icon="inline-start" />
          New Agent
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatsCard
          title="Total Meetings"
          value={totalMeetings}
          description={totalMeetings === 1 ? "1 meeting recorded" : `${totalMeetings} meetings recorded`}
          icon={Video}
        />
        <StatsCard
          title="Active Agents"
          value={activeAgents}
          description={activeAgents === 1 ? "1 agent configured" : `${activeAgents} agents configured`}
          icon={Bot}
        />
        <StatsCard
          title="Minutes Remaining"
          value={credits}
          description={credits > 0 ? `~${Math.floor(credits / 5)} meetings left` : "No minutes remaining"}
          icon={CreditCard}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Meetings</CardTitle>
        </CardHeader>
        <CardContent>
          {recentMeetings.length > 0 ? (
            <div className="space-y-3">
              {recentMeetings.map((meeting) => (
                <Link
                  key={meeting.id}
                  href={`/dashboard/meetings/${meeting.id}`}
                  className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">
                      {meeting.platform.charAt(0).toUpperCase() + meeting.platform.slice(1)} Meeting
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {meeting.platform} &middot; {new Date(meeting.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">
                      {meeting.duration_minutes ? `${Math.round(meeting.duration_minutes)} min` : "—"}
                    </span>
                    <Badge
                      variant={
                        meeting.status === "ended" ? "secondary" : meeting.status === "active" ? "default" : "outline"
                      }
                    >
                      {meeting.status}
                    </Badge>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 py-8">
              <Video className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No meetings yet</p>
              <p className="text-xs text-muted-foreground">
                Meetings will appear here once an agent joins a call.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
