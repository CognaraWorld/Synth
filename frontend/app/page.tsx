import { LandingPage } from "@/components/landing/LandingPage";

export const metadata = {
  title: "Cognara — AI That Joins Your Meetings",
  description:
    "An AI-powered meeting bot that joins Zoom, Microsoft Teams, and Google Meet as an active voice participant.",
};

export default function Home() {
  return (
    <div className="landing-bg text-[#1D1D1F] min-h-screen relative">
      <LandingPage />
    </div>
  );
}
