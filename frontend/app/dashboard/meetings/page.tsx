"use client";

import { useEffect, useState } from "react";
import { Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

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

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border py-16">
      <div className="rounded-full bg-muted p-3">
        <Video className="size-6 text-muted-foreground" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium">No meetings yet</p>
        <p className="text-sm text-muted-foreground">
          Meetings will appear here once an agent joins a call.
        </p>
      </div>
    </div>
  );
}

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMeetings() {
      try {
        const res = await fetch("/api/meetings");
        const json = await res.json();
        const data = json.data?.meetings ?? json.data ?? [];
        setMeetings(Array.isArray(data) ? data : []);
      } catch (err) {
        setError("Failed to load meetings. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    fetchMeetings();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Meetings</h1>
          <p className="text-sm text-muted-foreground">
            View transcripts and summaries from past meetings.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center gap-4 py-16">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const hasMeetings = meetings.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Meetings</h1>
        <p className="text-sm text-muted-foreground">
          View transcripts and summaries from past meetings.
        </p>
      </div>

      {hasMeetings ? (
        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Meeting</TableHead>
                <TableHead>Platform</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {meetings.map((meeting) => (
                <TableRow key={meeting.id}>
                  <TableCell className="font-medium">
                    {meeting.platform.charAt(0).toUpperCase() + meeting.platform.slice(1)} Meeting
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <Video className="size-3.5" />
                      {meeting.platform}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(meeting.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {meeting.duration_minutes ? `${Math.round(meeting.duration_minutes)} min` : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant={
                        meeting.status === "ended" ? "secondary" : "default"
                      }
                    >
                      {meeting.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
