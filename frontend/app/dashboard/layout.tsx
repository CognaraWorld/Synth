import { redirect } from "next/navigation";

import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { getCurrentSession } from "@/lib/auth/session";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // Gate the dashboard: require a signed-in session. Without this the page
  // throws "Not authenticated" from lib/data/dashboard.ts and the client-side
  // error boundary shows a "Try again" button instead of bouncing the user
  // to sign-in — a confusing UX for first-time visitors.
  const session = await getCurrentSession();
  if (!session?.user) {
    redirect("/api/auth/signin?callbackUrl=%2Fdashboard");
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Topbar userName={session.user.name ?? null} />
        <main className="flex-1 px-4 py-8 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
