import Link from "next/link";
import { FileDown, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatMeetingTime, formatMinutes } from "@/lib/utils";
import { ReportDTO } from "@/types";

export function ReportCard({ report }: { report: ReportDTO }) {
  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col gap-5 p-6">
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">{report.meetingTitle}</h3>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>{formatMeetingTime(report.scheduledTime)}</span>
            <span>{formatMinutes(report.durationMinutes)}</span>
          </div>
        </div>
        <p className="line-clamp-3 text-sm text-muted-foreground">{report.summary}</p>
        <div className="mt-auto flex flex-wrap gap-3">
          <Button asChild variant="outline">
            <Link href={`/dashboard/reports/${report.id}`}>
              <FileText className="h-4 w-4" />
              View report
            </Link>
          </Button>
          <Button asChild variant="ghost">
            <a href={report.pdfUrl}>
              <FileDown className="h-4 w-4" />
              PDF
            </a>
          </Button>
          <Button asChild variant="ghost">
            <a href={report.wordUrl}>
              <FileDown className="h-4 w-4" />
              Word
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
