import { getDashboardBillingData } from "@/lib/data/dashboard";
import { successResponse } from "@/lib/api-response";
import { notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  const data = await getDashboardBillingData();
  return successResponse(data);
}
