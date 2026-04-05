import Link from "next/link";
import { CalendarClock, ExternalLink, Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatMeetingTime } from "@/lib/utils";
import { MeetingDTO } from "@/types";

interface MeetingCardProps {
  meeting: MeetingDTO;
  compact?: boolean;
}

export function MeetingCard({ meeting, compact = false }: MeetingCardProps) {
  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-5 p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold">{meeting.title}</h3>
              <Badge variant={meeting.status === "LIVE" ? "success" : "secondary"}>{meeting.status}</Badge>
            </div>
            <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarClock className="h-4 w-4" />
              {formatMeetingTime(meeting.scheduledTime)}
            </div>
          </div>
          <Badge variant={meeting.botJoined ? "default" : "warning"}>{meeting.botJoined ? "Bot joined" : "Bot idle"}</Badge>
        </div>
        {!compact && meeting.notes ? <p className="text-sm text-muted-foreground">{meeting.notes}</p> : null}
        <div className="mt-auto flex flex-wrap items-center gap-3">
          <Button asChild className="flex-1 sm:flex-none">
            <a href={meeting.joinUrl} target="_blank" rel="noopener noreferrer">
              Join
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
          <Button variant="outline" className="flex-1 sm:flex-none">
            <Settings2 className="h-4 w-4" />
            Edit settings
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
