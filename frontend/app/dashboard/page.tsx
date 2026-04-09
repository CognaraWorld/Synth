import { getDashboardHomeData } from "@/lib/data/dashboard";
import { DashboardHomeClient } from "@/components/dashboard-home-client";

export default async function HomePage() {
  const data = await getDashboardHomeData();
  return <DashboardHomeClient data={data} />;
}
