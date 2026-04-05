import {
  BotProfileDTO,
  CalendarConnectionDTO,
  CalendarMeetingIndicator,
  DashboardHomeDTO,
  MeetingDTO,
  ReportDTO,
  UsageRecordDTO
} from "@/types";

export const sampleBotProfile: BotProfileDTO = {
  id: "bot_1",
  name: "Nova",
  persona: "Professional and strategic meeting copilot that answers crisply and drives decisions to closure.",
  voice: "FEMALE",
  responseMode: "WAKE_WORD_ONLY",
  createdAt: "2026-04-01T10:00:00.000Z",
  updatedAt: "2026-04-03T15:30:00.000Z",
  documents: [
    {
      id: "doc_1",
      name: "Pricing FAQ",
      fileName: "pricing-faq.pdf",
      fileType: "application/pdf",
      fileSize: 204800,
      fileUrl: "/uploads/pricing-faq.pdf",
      createdAt: "2026-04-02T09:00:00.000Z"
    },
    {
      id: "doc_2",
      name: "Implementation guide",
      fileName: "implementation-guide.docx",
      fileType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      fileSize: 144300,
      fileUrl: "/uploads/implementation-guide.docx",
      createdAt: "2026-04-02T09:00:00.000Z"
    }
  ]
};

export const sampleMeetings: MeetingDTO[] = [
  {
    id: "meeting_1",
    title: "Acme Weekly Product Sync",
    joinUrl: "https://meet.google.com/acme-product-sync",
    platform: "Google Meet",
    scheduledTime: "2026-04-04T09:30:00.000Z",
    endTime: "2026-04-04T10:15:00.000Z",
    status: "LIVE",
    durationMinutes: 45,
    botJoined: true,
    notes: "Focus on roadmap tradeoffs and launch blockers.",
    override: {
      id: "override_1",
      meetingId: "meeting_1",
      personaOverride: "Technical but concise product engineering advisor.",
      voiceOverride: "MALE",
      responseModeOverride: "PROACTIVE",
      documents: []
    }
  },
  {
    id: "meeting_2",
    title: "Enterprise Demo Prep",
    joinUrl: "https://zoom.us/j/enterprise-demo-prep",
    platform: "Zoom",
    scheduledTime: "2026-04-04T13:00:00.000Z",
    status: "SCHEDULED",
    durationMinutes: 30,
    botJoined: false,
    notes: "Review objection handling and pricing narrative."
  },
  {
    id: "meeting_3",
    title: "Board Narrative Review",
    joinUrl: "https://teams.microsoft.com/l/board-review",
    platform: "Microsoft Teams",
    scheduledTime: "2026-04-05T16:00:00.000Z",
    status: "SCHEDULED",
    durationMinutes: 60,
    botJoined: true
  },
  {
    id: "meeting_4",
    title: "Customer Discovery - Helio",
    joinUrl: "https://meet.google.com/customer-discovery-helio",
    platform: "Google Meet",
    scheduledTime: "2026-04-02T11:00:00.000Z",
    endTime: "2026-04-02T11:50:00.000Z",
    status: "COMPLETED",
    durationMinutes: 50,
    botJoined: true
  }
];

export const sampleReports: ReportDTO[] = [
  {
    id: "report_1",
    meetingId: "meeting_4",
    meetingTitle: "Customer Discovery - Helio",
    scheduledTime: "2026-04-02T11:00:00.000Z",
    durationMinutes: 50,
    summary:
      "Helio is interested in auto-joining implementation standups but needs stronger guardrails around security, bot wake-word control, and action-item export to existing systems.",
    actionItems: [
      { id: "ai_1", label: "Send security architecture overview", done: true, owner: "Ava" },
      { id: "ai_2", label: "Prepare pilot scope proposal", done: false, owner: "Rahul" },
      { id: "ai_3", label: "Confirm CRM export requirements", done: false, owner: "Maya" }
    ],
    pdfUrl: "/reports/helio.pdf",
    wordUrl: "/reports/helio.docx"
  },
  {
    id: "report_2",
    meetingId: "meeting_5",
    meetingTitle: "Revenue Strategy Review",
    scheduledTime: "2026-04-01T14:00:00.000Z",
    durationMinutes: 42,
    summary:
      "The team aligned on usage-based packaging and decided to test a higher-minute cap for enterprise plans before Q2 renewal conversations.",
    actionItems: [
      { id: "ai_4", label: "Draft enterprise pricing memo", done: true, owner: "Nina" },
      { id: "ai_5", label: "Model overage revenue scenarios", done: false, owner: "Sam" }
    ],
    pdfUrl: "/reports/revenue.pdf",
    wordUrl: "/reports/revenue.docx"
  },
  {
    id: "report_3",
    meetingId: "meeting_6",
    meetingTitle: "Support Ops Workflow",
    scheduledTime: "2026-03-30T17:00:00.000Z",
    durationMinutes: 35,
    summary:
      "Support wants the bot to draft follow-up recaps automatically and tag unresolved questions that require product or engineering input.",
    actionItems: [
      { id: "ai_6", label: "Define recap template variants", done: false, owner: "Elena" },
      { id: "ai_7", label: "Map unresolved issue routing", done: true, owner: "Chris" }
    ],
    pdfUrl: "/reports/support-ops.pdf",
    wordUrl: "/reports/support-ops.docx"
  }
];

export const sampleHomeData: DashboardHomeDTO = {
  stats: {
    minutesUsedThisMonth: 482,
    minutesRemaining: 1518,
    meetingsJoinedThisMonth: 14
  },
  upcomingMeetings: sampleMeetings.filter((meeting) => meeting.status === "SCHEDULED").slice(0, 3),
  recentReports: sampleReports.slice(0, 3)
};

export const sampleUsageRecords: UsageRecordDTO[] = [
  {
    id: "usage_1",
    meetingId: "meeting_4",
    meetingTitle: "Customer Discovery - Helio",
    minutesUsed: 50,
    usedAt: "2026-04-02T11:50:00.000Z"
  },
  {
    id: "usage_2",
    meetingId: "meeting_2",
    meetingTitle: "Revenue Strategy Review",
    minutesUsed: 42,
    usedAt: "2026-04-01T14:42:00.000Z"
  },
  {
    id: "usage_3",
    meetingId: "meeting_6",
    meetingTitle: "Support Ops Workflow",
    minutesUsed: 35,
    usedAt: "2026-03-30T17:35:00.000Z"
  }
];

export const sampleCalendarConnections: CalendarConnectionDTO[] = [
  {
    id: "calendar_1",
    provider: "GOOGLE",
    connectedAt: "2026-04-01T08:00:00.000Z",
    autoJoinAll: true
  }
];

export const sampleCalendarMeetings: CalendarMeetingIndicator[] = [
  {
    id: "calendar_meeting_1",
    title: "Acme Weekly Product Sync",
    start: "2026-04-04T09:30:00.000Z",
    end: "2026-04-04T10:15:00.000Z",
    botJoined: true
  },
  {
    id: "calendar_meeting_2",
    title: "Enterprise Demo Prep",
    start: "2026-04-04T13:00:00.000Z",
    end: "2026-04-04T13:30:00.000Z",
    botJoined: false
  },
  {
    id: "calendar_meeting_3",
    title: "Board Narrative Review",
    start: "2026-04-05T16:00:00.000Z",
    end: "2026-04-05T17:00:00.000Z",
    botJoined: true
  }
];
