"use client";

import { useMeetings } from "@/hooks/use-meetings";
import { useTranscriptSocket } from "@/hooks/use-transcript-socket";
import { PageHeader } from "@/components/page-header";
import { MeetingCard } from "@/components/meeting-card";
import { BotControlPanel } from "@/components/bot-control-panel";
import { TranscriptFeed } from "@/components/transcript-feed";
import { StartMeetingDialog } from "@/components/start-meeting-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";

export default function MeetingsPage() {
  const { data: meetings, isLoading } = useMeetings();

  const upcoming = meetings?.filter((m) => m.status === "SCHEDULED") ?? [];
  const live = meetings?.filter((m) => m.status === "LIVE") ?? [];
  const past = meetings?.filter((m) => m.status === "COMPLETED") ?? [];

  const liveMeeting = live[0];
  useTranscriptSocket(liveMeeting?.id ?? "");

  if (isLoading) {
    return (
      <div className="space-y-10">
        <Skeleton className="h-24 w-full rounded-3xl" />
        <Skeleton className="h-12 w-96 rounded-2xl" />
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 rounded-3xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Meetings"
        title="Your meetings"
        description="Manage upcoming, live, and past meetings."
        actions={<StartMeetingDialog />}
      />

      <Tabs defaultValue={live.length > 0 ? "live" : "upcoming"}>
        <TabsList>
          <TabsTrigger value="upcoming">Upcoming{upcoming.length > 0 ? ` (${upcoming.length})` : ""}</TabsTrigger>
          <TabsTrigger value="live">Live{live.length > 0 ? ` (${live.length})` : ""}</TabsTrigger>
          <TabsTrigger value="past">Past{past.length > 0 ? ` (${past.length})` : ""}</TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming">
          {upcoming.length === 0 ? (
            <EmptyState message="No upcoming meetings. Add one or connect your calendar." />
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {upcoming.map((meeting) => (
                <MeetingCard key={meeting.id} meeting={meeting} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="live">
          {live.length === 0 ? (
            <EmptyState message="No live meetings right now." />
          ) : (
            <div className="space-y-6">
              <MeetingCard meeting={liveMeeting} />
              <div className="grid gap-6 lg:grid-cols-2">
                <BotControlPanel meetingId={liveMeeting.id} />
                <TranscriptFeed />
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="past">
          {past.length === 0 ? (
            <EmptyState message="No past meetings yet." />
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {past.map((meeting) => (
                <MeetingCard key={meeting.id} meeting={meeting} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-border p-12 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
