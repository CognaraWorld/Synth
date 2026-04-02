import { Video } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const meetings = [
  {
    id: "1",
    title: "Product Sync",
    platform: "Google Meet",
    agent: "Note Taker",
    date: "2026-04-01",
    duration: "32 min",
    status: "completed" as const,
  },
  {
    id: "2",
    title: "Sprint Retrospective",
    platform: "Zoom",
    agent: "Standup Bot",
    date: "2026-03-31",
    duration: "45 min",
    status: "completed" as const,
  },
  {
    id: "3",
    title: "Client Demo",
    platform: "Teams",
    agent: "Sales Call Analyst",
    date: "2026-03-30",
    duration: "28 min",
    status: "processing" as const,
  },
  {
    id: "4",
    title: "Design Review",
    platform: "Google Meet",
    agent: "Note Taker",
    date: "2026-03-29",
    duration: "51 min",
    status: "completed" as const,
  },
  {
    id: "5",
    title: "Investor Update",
    platform: "Zoom",
    agent: "Sales Call Analyst",
    date: "2026-03-28",
    duration: "38 min",
    status: "completed" as const,
  },
];

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
                <TableHead>Agent</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {meetings.map((meeting) => (
                <TableRow
                  key={meeting.id}
                  className="cursor-pointer"
                >
                  <TableCell className="font-medium">
                    {meeting.title}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {meeting.platform}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {meeting.agent}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {meeting.date}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {meeting.duration}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant={
                        meeting.status === "completed" ? "secondary" : "outline"
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
