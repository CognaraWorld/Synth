import { getDashboardBillingData } from "@/lib/data/dashboard";
import { successResponse } from "@/lib/api-response";

export async function GET() {
  const data = await getDashboardBillingData();
  return successResponse(data);
}
