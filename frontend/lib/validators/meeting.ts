import { z } from "zod";

export const createMeetingSchema = z.object({
  title: z.string().min(2).max(100).optional(),
  joinUrl: z.string().url(),
  scheduledTime: z.string().datetime().optional(),
  platform: z.enum(["Zoom", "Google Meet", "Microsoft Teams", "Manual"]).default("Manual")
});

export const meetingOverrideSchema = z.object({
  personaOverride: z.string().max(500).optional().nullable(),
  voiceOverride: z.enum(["MALE", "FEMALE"]).optional().nullable(),
  responseModeOverride: z.enum(["WAKE_WORD_ONLY", "PROACTIVE"]).optional().nullable()
});
