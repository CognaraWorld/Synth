import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  console.log("Seeding database...");

  // Demo user
  const user = await prisma.user.upsert({
    where: { email: "demo@meetingbot.dev" },
    update: {},
    create: {
      id: "demo-user",
      name: "Demo User",
      email: "demo@meetingbot.dev"
    }
  });

  // Bot profile
  const botProfile = await prisma.botProfile.upsert({
    where: { userId: user.id },
    update: {},
    create: {
      id: "bot_1",
      userId: user.id,
      name: "Nova",
      persona:
        "Professional and strategic meeting copilot that answers crisply and drives decisions to closure.",
      voice: "FEMALE",
      responseMode: "WAKE_WORD_ONLY"
    }
  });

  // Global documents
  const docsData = [
    {
      id: "doc_1",
      botProfileId: botProfile.id,
      name: "Pricing FAQ",
      fileName: "pricing-faq.pdf",
      fileType: "application/pdf",
      fileSize: 204800,
      fileUrl: "/uploads/pricing-faq.pdf"
    },
    {
      id: "doc_2",
      botProfileId: botProfile.id,
      name: "Implementation guide",
      fileName: "implementation-guide.docx",
      fileType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      fileSize: 144300,
      fileUrl: "/uploads/implementation-guide.docx"
    }
  ];

  for (const doc of docsData) {
    await prisma.globalDocument.upsert({
      where: { id: doc.id },
      update: {},
      create: doc
    });
  }

  // Meetings
  const meetingsData = [
    {
      id: "meeting_1",
      userId: user.id,
      title: "Acme Weekly Product Sync",
      joinUrl: "https://meet.google.com/acme-product-sync",
      platform: "Google Meet",
      scheduledTime: new Date("2026-04-04T09:30:00.000Z"),
      endTime: new Date("2026-04-04T10:15:00.000Z"),
      status: "LIVE",
      durationMinutes: 45,
      botJoined: true,
      notes: "Focus on roadmap tradeoffs and launch blockers."
    },
    {
      id: "meeting_2",
      userId: user.id,
      title: "Enterprise Demo Prep",
      joinUrl: "https://zoom.us/j/enterprise-demo-prep",
      platform: "Zoom",
      scheduledTime: new Date("2026-04-04T13:00:00.000Z"),
      status: "SCHEDULED",
      durationMinutes: 30,
      botJoined: false,
      notes: "Review objection handling and pricing narrative."
    },
    {
      id: "meeting_3",
      userId: user.id,
      title: "Board Narrative Review",
      joinUrl: "https://teams.microsoft.com/l/board-review",
      platform: "Microsoft Teams",
      scheduledTime: new Date("2026-04-05T16:00:00.000Z"),
      status: "SCHEDULED",
      durationMinutes: 60,
      botJoined: true
    },
    {
      id: "meeting_4",
      userId: user.id,
      title: "Customer Discovery - Helio",
      joinUrl: "https://meet.google.com/customer-discovery-helio",
      platform: "Google Meet",
      scheduledTime: new Date("2026-04-02T11:00:00.000Z"),
      endTime: new Date("2026-04-02T11:50:00.000Z"),
      status: "COMPLETED",
      durationMinutes: 50,
      botJoined: true
    },
    {
      id: "meeting_5",
      userId: user.id,
      title: "Revenue Strategy Review",
      joinUrl: "https://meet.google.com/revenue-strategy",
      platform: "Google Meet",
      scheduledTime: new Date("2026-04-01T14:00:00.000Z"),
      endTime: new Date("2026-04-01T14:42:00.000Z"),
      status: "COMPLETED",
      durationMinutes: 42,
      botJoined: true
    },
    {
      id: "meeting_6",
      userId: user.id,
      title: "Support Ops Workflow",
      joinUrl: "https://zoom.us/j/support-ops",
      platform: "Zoom",
      scheduledTime: new Date("2026-03-30T17:00:00.000Z"),
      endTime: new Date("2026-03-30T17:35:00.000Z"),
      status: "COMPLETED",
      durationMinutes: 35,
      botJoined: true
    }
  ];

  for (const meeting of meetingsData) {
    await prisma.meeting.upsert({
      where: { id: meeting.id },
      update: {},
      create: meeting
    });
  }

  // Meeting override for the live meeting
  await prisma.meetingOverride.upsert({
    where: { meetingId: "meeting_1" },
    update: {},
    create: {
      id: "override_1",
      meetingId: "meeting_1",
      personaOverride: "Technical but concise product engineering advisor.",
      voiceOverride: "MALE",
      responseModeOverride: "PROACTIVE"
    }
  });

  // Live session
  await prisma.liveSession.upsert({
    where: { meetingId: "meeting_1" },
    update: {},
    create: {
      id: "live_1",
      meetingId: "meeting_1",
      status: "LISTENING"
    }
  });

  // Reports
  const reportsData = [
    {
      id: "report_1",
      meetingId: "meeting_4",
      summary:
        "Helio is interested in auto-joining implementation standups but needs stronger guardrails around security, bot wake-word control, and action-item export to existing systems.",
      actionItems: JSON.stringify([
        { id: "ai_1", label: "Send security architecture overview", done: true, owner: "Ava" },
        { id: "ai_2", label: "Prepare pilot scope proposal", done: false, owner: "Rahul" },
        { id: "ai_3", label: "Confirm CRM export requirements", done: false, owner: "Maya" }
      ]),
      pdfUrl: "/reports/helio.pdf",
      wordUrl: "/reports/helio.docx"
    },
    {
      id: "report_2",
      meetingId: "meeting_5",
      summary:
        "The team aligned on usage-based packaging and decided to test a higher-minute cap for enterprise plans before Q2 renewal conversations.",
      actionItems: JSON.stringify([
        { id: "ai_4", label: "Draft enterprise pricing memo", done: true, owner: "Nina" },
        { id: "ai_5", label: "Model overage revenue scenarios", done: false, owner: "Sam" }
      ]),
      pdfUrl: "/reports/revenue.pdf",
      wordUrl: "/reports/revenue.docx"
    },
    {
      id: "report_3",
      meetingId: "meeting_6",
      summary:
        "Support wants the bot to draft follow-up recaps automatically and tag unresolved questions that require product or engineering input.",
      actionItems: JSON.stringify([
        { id: "ai_6", label: "Define recap template variants", done: false, owner: "Elena" },
        { id: "ai_7", label: "Map unresolved issue routing", done: true, owner: "Chris" }
      ]),
      pdfUrl: "/reports/support-ops.pdf",
      wordUrl: "/reports/support-ops.docx"
    }
  ];

  for (const report of reportsData) {
    await prisma.report.upsert({
      where: { id: report.id },
      update: {},
      create: report
    });
  }

  // Usage records
  const usageData = [
    {
      id: "usage_1",
      userId: user.id,
      meetingId: "meeting_4",
      meetingTitle: "Customer Discovery - Helio",
      minutesUsed: 50,
      usedAt: new Date("2026-04-02T11:50:00.000Z")
    },
    {
      id: "usage_2",
      userId: user.id,
      meetingId: "meeting_5",
      meetingTitle: "Revenue Strategy Review",
      minutesUsed: 42,
      usedAt: new Date("2026-04-01T14:42:00.000Z")
    },
    {
      id: "usage_3",
      userId: user.id,
      meetingId: "meeting_6",
      meetingTitle: "Support Ops Workflow",
      minutesUsed: 35,
      usedAt: new Date("2026-03-30T17:35:00.000Z")
    }
  ];

  for (const record of usageData) {
    await prisma.usageRecord.upsert({
      where: { id: record.id },
      update: {},
      create: record
    });
  }

  // Calendar connection
  await prisma.calendarConnection.upsert({
    where: { id: "calendar_1" },
    update: {},
    create: {
      id: "calendar_1",
      userId: user.id,
      provider: "GOOGLE",
      autoJoinAll: true
    }
  });

  console.log("Seed complete!");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
