import { Brain, CalendarDays, CreditCard, Home, Mic2, ScrollText } from "lucide-react";

export const dashboardNav = [
  { title: "Home", href: "/dashboard", icon: Home },
  { title: "My Bot", href: "/dashboard/bot", icon: Mic2 },
  { title: "Meetings", href: "/dashboard/meetings", icon: Brain },
  { title: "Calendar", href: "/dashboard/calendar", icon: CalendarDays },
  { title: "Reports", href: "/dashboard/reports", icon: ScrollText },
  { title: "Billing", href: "/dashboard/billing", icon: CreditCard }
] as const;

export const personaPresets = [
  "Professional",
  "Friendly",
  "Technical",
  "Strategic",
  "Research Assistant"
] as const;

export const responseModeOptions = [
  {
    value: "WAKE_WORD_ONLY",
    label: "Respond only when called by name",
    description: "The bot only speaks when someone uses the wake word."
  },
  {
    value: "PROACTIVE",
    label: "Proactive contributions",
    description: "The bot can volunteer clarifications and surface insights when helpful."
  }
] as const;

export const voiceOptions = [
  { value: "MALE", label: "Male" },
  { value: "FEMALE", label: "Female" }
] as const;
