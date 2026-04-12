"use client";

import { useState } from "react";
import { MessageSquare } from "lucide-react";
import { ChatSidebar } from "@/components/chat-sidebar";
import { PageHeader } from "@/components/page-header";
import { StatsCard } from "@/components/stats-card";
import { MeetingCard } from "@/components/meeting-card";
import { ReportCard } from "@/components/report-card";
import { StartMeetingDialog } from "@/components/start-meeting-dialog";
import { Button } from "@/components/ui/button";
import { formatMinutes } from "@/lib/utils";
import type { DashboardHomeDTO } from "@/types";

export function DashboardHomeClient({ data }: { data: DashboardHomeDTO }) {
  const [crossChatOpen, setCrossChatOpen] = useState(false);

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Dashboard"
        title="Welcome back"
        description="Your AI meeting copilot is ready."
        actions={
          <>
            <Button variant="outline" onClick={() => setCrossChatOpen(true)}>
              <MessageSquare className="h-4 w-4" />
              Chat across meetings
            </Button>
            <StartMeetingDialog />
          </>
        }
      />

      <div className="grid gap-6 md:grid-cols-3">
        <StatsCard
          label="Minutes used"
          value={formatMinutes(data.stats.minutesUsedThisMonth)}
          delta="this month"
        />
        <StatsCard
          label="Minutes remaining"
          value={formatMinutes(data.stats.minutesRemaining)}
          delta={`${data.stats.minutesRemaining.toLocaleString()} of 2,000`}
        />
        <StatsCard
          label="Meetings joined"
          value={String(data.stats.meetingsJoinedThisMonth)}
          delta="this month"
        />
      </div>

      <section className="space-y-6">
        <h2 className="text-xl font-semibold">Upcoming Meetings</h2>
        {data.upcomingMeetings.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-border p-12 text-center">
            <p className="text-sm text-muted-foreground">
              No upcoming meetings scheduled. Connect your calendar or start one manually.
            </p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {data.upcomingMeetings.map((meeting) => (
              <MeetingCard key={meeting.id} meeting={meeting} compact />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-6">
        <h2 className="text-xl font-semibold">Recent Reports</h2>
        {data.recentReports.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-border p-12 text-center">
            <p className="text-sm text-muted-foreground">
              No reports yet. Reports are generated automatically after each meeting.
            </p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {data.recentReports.map((report) => (
              <ReportCard key={report.id} report={report} />
            ))}
          </div>
        )}
      </section>

      <ChatSidebar
        meetingId="cross-meeting"
        isOpen={crossChatOpen}
        onClose={() => setCrossChatOpen(false)}
        crossMeeting
      />
    </div>
  );
}
