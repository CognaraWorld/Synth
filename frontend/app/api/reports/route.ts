import { getReports } from "@/lib/data/reports";
import { successResponse } from "@/lib/api-response";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const reports = await getReports();
    return successResponse(reports);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load reports");
  }
}
