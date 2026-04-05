import { z } from "zod";

export const botProfileSchema = z.object({
  name: z.string().min(2).max(50),
  persona: z.string().min(10).max(500),
  voice: z.enum(["MALE", "FEMALE"]),
  responseMode: z.enum(["WAKE_WORD_ONLY", "PROACTIVE"])
});

export const onboardingSchema = botProfileSchema.extend({
  customPersona: z.string().optional()
});
