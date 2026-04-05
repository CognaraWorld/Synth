"use client";

import { useState } from "react";
import { CheckCircle2, Circle, FileDown, MessageSquare } from "lucide-react";
import { ChatSidebar } from "@/components/chat-sidebar";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatMeetingTime, formatMinutes } from "@/lib/utils";
import type { ReportDTO } from "@/types";

export function ReportDetailClient({ report }: { report: ReportDTO }) {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Reports"
        title={report.meetingTitle}
        description={`${formatMeetingTime(report.scheduledTime)} | ${formatMinutes(report.durationMinutes)}`}
        actions={
          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setChatOpen(true)}>
              <MessageSquare className="h-4 w-4" />
              Chat about this meeting
            </Button>
            <Button asChild variant="outline">
              <a href={report.pdfUrl}>
                <FileDown className="h-4 w-4" />
                PDF
              </a>
            </Button>
            <Button asChild variant="outline">
              <a href={report.wordUrl}>
                <FileDown className="h-4 w-4" />
                Word
              </a>
            </Button>
          </div>
        }
      />

      <div className="grid gap-8 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="leading-relaxed text-muted-foreground">{report.summary}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Action Items</CardTitle>
              <Badge>{report.actionItems.length}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {report.actionItems.map((item) => (
                <div key={item.id} className="flex items-start gap-3">
                  {item.done ? (
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" />
                  ) : (
                    <Circle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                  )}
                  <div>
                    <p className={`text-sm ${item.done ? "text-muted-foreground line-through" : ""}`}>{item.label}</p>
                    {item.owner ? <p className="mt-0.5 text-xs text-muted-foreground">{item.owner}</p> : null}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <ChatSidebar meetingId={report.meetingId} isOpen={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
