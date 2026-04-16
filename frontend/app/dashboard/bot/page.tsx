import { getBotProfile } from "@/lib/data/bot-profile";
import { BotFormClient } from "./bot-form-client";

export default async function BotPage() {
  const bot = await getBotProfile();
  return <BotFormClient initialBot={bot} />;
}
