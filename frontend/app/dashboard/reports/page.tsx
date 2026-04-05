"use client";

import { useReports } from "@/hooks/use-reports";
import { PageHeader } from "@/components/page-header";
import { ReportCard } from "@/components/report-card";
import { Skeleton } from "@/components/ui/skeleton";

export default function ReportsPage() {
  const { data: reports, isLoading } = useReports();

  if (isLoading) {
    return (
      <div className="space-y-10">
        <Skeleton className="h-24 w-full rounded-3xl" />
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-64 rounded-3xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Reports"
        title="Meeting Reports"
        description="Summaries, action items, and transcripts from your meetings."
      />

      {!reports || reports.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-border p-12 text-center">
          <p className="text-sm text-muted-foreground">No reports yet. Reports are generated after each meeting.</p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {reports.map((report) => (
            <ReportCard key={report.id} report={report} />
          ))}
        </div>
      )}
    </div>
  );
}
