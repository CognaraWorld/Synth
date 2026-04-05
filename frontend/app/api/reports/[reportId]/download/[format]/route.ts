import { backendFetch } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET(_: Request, { params }: { params: { reportId: string; format: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const response = await backendFetch(`/api/reports/${params.reportId}/download/${params.format}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const headers = new Headers();
    const contentType = response.headers.get("content-type");
    const contentDisposition = response.headers.get("content-disposition");

    if (contentType) {
      headers.set("Content-Type", contentType);
    }

    if (contentDisposition) {
      headers.set("Content-Disposition", contentDisposition);
    }

    return new Response(response.body, {
      status: response.status,
      headers
    });
  } catch (error) {
    return backendErrorResponse(error, "Failed to download report");
  }
}
