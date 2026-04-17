import { getDashboardBillingData } from "@/lib/data/dashboard";
import { successResponse } from "@/lib/api-response";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const data = await getDashboardBillingData();
    return successResponse(data);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load billing data");
  }
}
