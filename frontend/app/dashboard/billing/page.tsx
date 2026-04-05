import { CreditCard, Zap } from "lucide-react";
import { getDashboardBillingData } from "@/lib/data/dashboard";
import { BuyCreditsSection } from "@/components/buy-credits-section";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatMinutes, formatMeetingTime } from "@/lib/utils";

export default async function BillingPage() {
  const { stats, usageRecords } = await getDashboardBillingData();
  const usagePercent = (stats.minutesUsedThisMonth / 2000) * 100;

  return (
    <div className="space-y-10">
      <PageHeader eyebrow="Billing" title="Plan & Usage" description="Monitor your usage and manage your subscription." />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15">
                <CreditCard className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Current plan</p>
                <p className="text-xl font-semibold">Pro</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardContent className="space-y-4 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Minutes this month</p>
                <p className="text-2xl font-semibold">
                  {formatMinutes(stats.minutesUsedThisMonth)}{" "}
                  <span className="text-base font-normal text-muted-foreground">/ 2,000 min</span>
                </p>
              </div>
              <Badge variant={usagePercent > 80 ? "warning" : "success"}>
                {stats.minutesRemaining.toLocaleString()} min remaining
              </Badge>
            </div>
            <Progress value={usagePercent} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Usage Breakdown</CardTitle>
            <Button variant="outline">
              <Zap className="h-4 w-4" />
              Upgrade Plan
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {usageRecords.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No usage recorded this month.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Meeting</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Minutes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usageRecords.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="font-medium">{record.meetingTitle}</TableCell>
                    <TableCell>{formatMeetingTime(record.usedAt)}</TableCell>
                    <TableCell className="text-right">{record.minutesUsed}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <BuyCreditsSection />
    </div>
  );
}
