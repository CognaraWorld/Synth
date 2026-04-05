import { getCalendarData } from "@/lib/data/dashboard";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { CalendarDays, Link2 } from "lucide-react";
import { format, startOfWeek, addDays } from "date-fns";

export default async function CalendarPage() {
  const data = await getCalendarData();

  const today = new Date();
  const weekStart = startOfWeek(today, { weekStartsOn: 1 });
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Calendar"
        title="Calendar Integration"
        description="Connect your calendar and manage auto-join settings."
      />

      <div className="grid gap-6 md:grid-cols-2">
        <CalendarConnectionCard
          provider="Google Calendar"
          connected={data.connections.some((c) => c.provider === "GOOGLE")}
          autoJoinAll={data.connections.find((c) => c.provider === "GOOGLE")?.autoJoinAll ?? false}
        />
        <CalendarConnectionCard
          provider="Outlook"
          connected={data.connections.some((c) => c.provider === "OUTLOOK")}
          autoJoinAll={data.connections.find((c) => c.provider === "OUTLOOK")?.autoJoinAll ?? false}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>This Week</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-3">
            {weekDays.map((day) => {
              const dayStr = format(day, "yyyy-MM-dd");
              const dayMeetings = data.meetings.filter(
                (m) => format(new Date(m.start), "yyyy-MM-dd") === dayStr
              );
              const isToday = format(today, "yyyy-MM-dd") === dayStr;

              return (
                <div
                  key={dayStr}
                  className={`min-h-[120px] rounded-2xl border p-3 ${
                    isToday ? "border-primary bg-primary/5" : "border-border"
                  }`}
                >
                  <p className="text-xs font-medium text-muted-foreground">{format(day, "EEE")}</p>
                  <p className={`text-lg font-semibold ${isToday ? "text-primary" : ""}`}>{format(day, "d")}</p>
                  <div className="mt-2 space-y-1.5">
                    {dayMeetings.map((meeting) => (
                      <div key={meeting.id} className="rounded-lg bg-secondary/70 p-1.5 text-xs">
                        <p className="truncate font-medium">{meeting.title}</p>
                        <Badge
                          variant={meeting.botJoined ? "success" : "secondary"}
                          className="mt-1 px-1.5 py-0 text-[10px]"
                        >
                          {meeting.botJoined ? "Bot" : "No bot"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CalendarConnectionCard({
  provider,
  connected,
  autoJoinAll
}: {
  provider: string;
  connected: boolean;
  autoJoinAll: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4 p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-secondary">
            <CalendarDays className="h-6 w-6" />
          </div>
          <div>
            <p className="font-medium">{provider}</p>
            <p className="text-sm text-muted-foreground">{connected ? "Connected" : "Not connected"}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {connected && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground">Auto-join</label>
              <Switch checked={autoJoinAll} />
            </div>
          )}
          <Button variant={connected ? "outline" : "default"} size="sm">
            <Link2 className="h-4 w-4" />
            {connected ? "Manage" : "Connect"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
