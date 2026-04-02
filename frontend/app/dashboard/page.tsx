import Link from "next/link";
import { Video, Bot, CreditCard, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatsCard } from "@/components/dashboard/stats-card";

const recentMeetings = [
  {
    id: "1",
    title: "Product Sync",
    platform: "Google Meet",
    date: "2026-04-01",
    duration: "32 min",
    status: "completed",
  },
  {
    id: "2",
    title: "Sprint Retrospective",
    platform: "Zoom",
    date: "2026-03-31",
    duration: "45 min",
    status: "completed",
  },
  {
    id: "3",
    title: "Client Demo",
    platform: "Microsoft Teams",
    date: "2026-03-30",
    duration: "28 min",
    status: "processing",
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Overview of your meetings and agents.
          </p>
        </div>
        <Button render={<Link href="/dashboard/agents/new" />}>
          <Plus className="size-4" data-icon="inline-start" />
          New Agent
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatsCard
          title="Total Meetings"
          value={24}
          description="+3 this week"
          icon={Video}
        />
        <StatsCard
          title="Active Agents"
          value={3}
          description="1 custom, 2 general"
          icon={Bot}
        />
        <StatsCard
          title="Credits Remaining"
          value={120}
          description="~40 meetings left"
          icon={CreditCard}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Meetings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {recentMeetings.map((meeting) => (
              <div
                key={meeting.id}
                className="flex items-center justify-between rounded-lg border border-border p-3"
              >
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium">{meeting.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {meeting.platform} &middot; {meeting.date}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {meeting.duration}
                  </span>
                  <Badge
                    variant={
                      meeting.status === "completed" ? "secondary" : "outline"
                    }
                  >
                    {meeting.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
