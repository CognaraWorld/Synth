import { getReports } from "@/lib/data/reports";
import { successResponse } from "@/lib/api-response";

export async function GET() {
  const reports = await getReports();
  return successResponse(reports);
}
