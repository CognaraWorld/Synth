import { getReports } from "@/lib/data/reports";
import { successResponse } from "@/lib/api-response";
import { notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  const reports = await getReports();
  return successResponse(reports);
}
