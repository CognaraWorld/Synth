import { WebSocketServer } from "ws";

const PORT = process.env.WS_PORT ?? 3001;

const wss = new WebSocketServer({ port: Number(PORT), path: "/transcripts" });

console.log(`Transcript WebSocket server running on ws://localhost:${PORT}/transcripts`);

const speakers = ["Alice", "Bob", "Charlie"];
const botName = "Nova";
const phrases = [
  "I think we should focus on the Q2 roadmap first.",
  "That's a great point. What about the pricing change?",
  "Let me pull up the numbers from last quarter.",
  "We need to decide on the enterprise tier before Thursday.",
  "I'll draft the proposal and share it by end of day.",
  "Can we revisit the onboarding flow? There are some drop-off issues.",
  "The integration with Salesforce is almost done.",
  "Security review is scheduled for next Monday.",
  "Let's table that and move to the next agenda item.",
  "I agree, we should prioritize the customer feedback loop."
];

const botPhrases = [
  "Based on the data I've seen, usage grew 34% month over month.",
  "The last time this topic came up, the team decided to defer to Q3.",
  "I can see three action items from this discussion so far.",
  "The pricing FAQ document mentions a 15% discount for annual plans.",
  "Would you like me to summarize the key decisions made so far?"
];

wss.on("connection", (ws, req) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const sessionId = url.searchParams.get("sessionId");
  console.log(`Client connected for session: ${sessionId}`);

  let chunkIndex = 0;

  const interval = setInterval(() => {
    const isBotSpeaker = Math.random() > 0.7;
    const speaker = isBotSpeaker ? botName : speakers[Math.floor(Math.random() * speakers.length)];
    const pool = isBotSpeaker ? botPhrases : phrases;
    const text = pool[Math.floor(Math.random() * pool.length)];

    const chunk = {
      type: "chunk",
      payload: {
        id: `chunk_${Date.now()}_${chunkIndex++}`,
        speaker,
        text,
        timestamp: new Date().toISOString(),
        isBot: isBotSpeaker
      }
    };

    ws.send(JSON.stringify(chunk));
  }, 3000 + Math.random() * 4000);

  const statusInterval = setInterval(() => {
    const statuses = ["LISTENING", "THINKING", "SPEAKING", "LISTENING"];
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    ws.send(JSON.stringify({ type: "status", payload: { status } }));
  }, 8000 + Math.random() * 5000);

  ws.on("close", () => {
    console.log(`Client disconnected from session: ${sessionId}`);
    clearInterval(interval);
    clearInterval(statusInterval);
  });

  ws.on("error", (err) => {
    console.error(`WebSocket error for session ${sessionId}:`, err.message);
    clearInterval(interval);
    clearInterval(statusInterval);
  });
});
