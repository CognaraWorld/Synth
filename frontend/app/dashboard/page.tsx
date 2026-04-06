"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Video, Bot, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatsCard } from "@/components/stats-card";
import { Skeleton } from "@/components/ui/skeleton";

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

export default function DashboardPage() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [userRes, meetingsRes] = await Promise.all([
          fetch("/api/bot-profile").then((r) => r.json()),
          fetch("/api/meetings").then((r) => r.json()),
        ]);
        setUser(userRes.data ?? null);
        const meetingsList = meetingsRes.data?.meetings ?? meetingsRes.data ?? [];
        setMeetings(Array.isArray(meetingsList) ? meetingsList : []);
      } catch {
        setError("Failed to load dashboard data. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
        <Skeleton className="h-64" />
      </div>
    );
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
  const credits = user?.credits ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of your meetings and usage.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatsCard
          label="Total Meetings"
          value={String(totalMeetings)}
          delta={totalMeetings === 1 ? "1 meeting recorded" : `${totalMeetings} meetings recorded`}
        />
        <StatsCard
          label="Minutes Remaining"
          value={String(credits)}
          delta={credits > 0 ? `~${Math.floor(credits / 5)} meetings left` : "No minutes remaining"}
        />
        <StatsCard
          label="Active Bot"
          value={user ? "Configured" : "—"}
          delta="Manage on Bot page"
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
                <div
                  key={meeting.id}
                  className="flex items-center justify-between rounded-lg border border-border p-3"
                >
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">
                      {meeting.platform.charAt(0).toUpperCase() + meeting.platform.slice(1)} Meeting
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(meeting.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">
                      {meeting.duration_minutes ? `${Math.round(meeting.duration_minutes)} min` : "—"}
                    </span>
                    <Badge variant={meeting.status === "ended" ? "secondary" : "default"}>
                      {meeting.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 py-8">
              <Video className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No meetings yet</p>
              <p className="text-xs text-muted-foreground">
                Meetings will appear here once you start a meeting.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
