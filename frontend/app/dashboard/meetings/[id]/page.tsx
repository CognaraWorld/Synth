"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { ArrowLeft, Clock, Download, FileText, Loader2, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface Meeting {
  id: string;
  title: string;
  platform: string;
  agent_name?: string;
  date: string;
  duration: string;
  status: "completed" | "processing" | "failed";
  transcript?: string;
  summary?: {
    key_points?: string[];
    action_items?: string[];
    decisions?: string[];
  };
}

function StatusBadge({ status }: { status: Meeting["status"] }) {
  const variantMap: Record<Meeting["status"], "secondary" | "outline" | "destructive"> = {
    completed: "secondary",
    processing: "outline",
    failed: "destructive",
  };
  return <Badge variant={variantMap[status]}>{status}</Badge>;
}

function PlatformIcon({ platform }: { platform: string }) {
  const label = platform.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <Badge variant="outline" className="gap-1.5">
      <Video className="size-3" />
      {label}
    </Badge>
  );
}

export default function MeetingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMeeting = useCallback(async () => {
    try {
      const { getMeeting } = await import("@/lib/api");
      const data = await getMeeting(id);
      setMeeting(data);
    } catch {
      // TODO: Handle error state
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchMeeting();
  }, [fetchMeeting]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5"
          nativeButton={false} render={<Link href="/dashboard/meetings" />}
        >
          <ArrowLeft className="size-3.5" />
          Back to Meetings
        </Button>
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-border py-16">
          <Video className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Meeting not found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Navigation */}
      <Button
        variant="ghost"
        size="sm"
        className="gap-1.5"
        nativeButton={false} render={<Link href="/dashboard/meetings" />}
      >
        <ArrowLeft className="size-3.5" />
        Back to Meetings
      </Button>

      {/* Meeting Header */}
      <div className="space-y-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold tracking-tight">
              {meeting.title}
            </h1>
            {meeting.agent_name && (
              <p className="text-sm text-muted-foreground">
                Agent: {meeting.agent_name}
              </p>
            )}
          </div>
          <StatusBadge status={meeting.status} />
        </div>
        <div className="flex items-center gap-3">
          <PlatformIcon platform={meeting.platform} />
          <Badge variant="outline" className="gap-1.5">
            <Clock className="size-3" />
            {meeting.duration}
          </Badge>
          <span className="text-sm text-muted-foreground">{meeting.date}</span>
        </div>
      </div>

      <Separator />

      {/* Transcript */}
      <Card>
        <CardHeader>
          <CardTitle>Transcript</CardTitle>
          <CardDescription>
            Full transcript of the meeting conversation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {meeting.transcript ? (
            <div className="max-h-96 overflow-y-auto rounded-lg bg-muted/50 p-4">
              <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                {meeting.transcript}
              </pre>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-10">
              <FileText className="size-5 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {meeting.status === "processing"
                  ? "Transcript is being generated..."
                  : "No transcript available for this meeting."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Summary</CardTitle>
          <CardDescription>
            Key takeaways and action items from this meeting.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {meeting.summary ? (
            <div className="space-y-5">
              {meeting.summary.key_points &&
                meeting.summary.key_points.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium">Key Points</h3>
                    <ul className="space-y-1.5">
                      {meeting.summary.key_points.map((point, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-sm text-muted-foreground"
                        >
                          <span className="mt-1 block size-1.5 shrink-0 rounded-full bg-primary" />
                          {point}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {meeting.summary.action_items &&
                meeting.summary.action_items.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium">Action Items</h3>
                    <ul className="space-y-1.5">
                      {meeting.summary.action_items.map((item, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-sm text-muted-foreground"
                        >
                          <span className="mt-1 block size-1.5 shrink-0 rounded-full bg-chart-2" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

              {meeting.summary.decisions &&
                meeting.summary.decisions.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium">Decisions</h3>
                    <ul className="space-y-1.5">
                      {meeting.summary.decisions.map((decision, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-sm text-muted-foreground"
                        >
                          <span className="mt-1 block size-1.5 shrink-0 rounded-full bg-chart-4" />
                          {decision}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-10">
              <FileText className="size-5 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {meeting.status === "processing"
                  ? "Summary is being generated..."
                  : "No summary available for this meeting."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Download Buttons */}
      <Card>
        <CardHeader>
          <CardTitle>Export</CardTitle>
          <CardDescription>
            Download the transcript and summary in your preferred format.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Button variant="outline" className="gap-1.5" disabled>
              <Download className="size-3.5" data-icon="inline-start" />
              Download PDF
            </Button>
            <Button variant="outline" className="gap-1.5" disabled>
              <Download className="size-3.5" data-icon="inline-start" />
              Download Word
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Export options will be available once the transcript is finalized.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
