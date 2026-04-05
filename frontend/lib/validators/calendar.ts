import { z } from "zod";

export const calendarConnectionSchema = z.object({
  provider: z.enum(["GOOGLE", "OUTLOOK"]),
  autoJoinAll: z.boolean().default(false)
});
