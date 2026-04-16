import { notFound } from "next/navigation";
import { ReportDetailClient } from "@/components/report-detail-client";
import { getReportById } from "@/lib/data/reports";

export default async function ReportDetailPage({ params }: { params: { id: string } }) {
  const report = await getReportById(params.id);
  if (!report) {
    notFound();
  }
  return <ReportDetailClient report={report} />;
}
