"use client";

import { useState } from "react";
import { MessageSquare, Mic, MicOff, PhoneOff, SendHorizonal, Square } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useChatInsights } from "@/hooks/use-chat-insights";
import { useLiveControls } from "@/hooks/use-live-controls";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useTranscriptStore } from "@/stores/transcript-store";

export function BotControlPanel({
  botName = "Nova",
  meetingId,
  onOpenChat,
}: {
  botName?: string;
  meetingId?: string;
  onOpenChat?: () => void;
}) {
  const [instruction, setInstruction] = useState("");
  const queryClient = useQueryClient();
  const controls = useLiveControls(meetingId ?? "");
  const { unreadCount, clearUnread } = useChatInsights(meetingId, !!meetingId);
  const status = useTranscriptStore((state) => state.status);
  const setStatus = useTranscriptStore((state) => state.setStatus);
  const addChunk = useTranscriptStore((state) => state.addChunk);
  const reset = useTranscriptStore((state) => state.reset);

  async function handleMuteToggle() {
    const previousStatus = status;
    const shouldMute = status !== "MUTED";
    setStatus(shouldMute ? "MUTED" : "LISTENING");

    if (!meetingId) return;

    try {
      if (shouldMute) {
        await controls.mute();
      } else {
        await controls.unmute();
      }
    } catch {
      setStatus(previousStatus);
    }
  }

  async function handleStopSpeaking() {
    const previousStatus = status;
    setStatus("LISTENING");

    if (!meetingId) return;

    try {
      await controls.stopSpeaking();
    } catch {
      setStatus(previousStatus);
    }
  }

  async function handleLeave() {
    const previousStatus = status;
    setStatus("MUTED");

    if (!meetingId) return;

    try {
      await controls.leave();
      reset();
      await queryClient.invalidateQueries({ queryKey: ["meetings"] });
      await queryClient.invalidateQueries({ queryKey: ["live-session", meetingId] });
    } catch {
      setStatus(previousStatus);
    }
  }

  async function handleSendInstruction() {
    if (!instruction) {
      return;
    }

    const nextInstruction = instruction;
    const previousStatus = status;

    addChunk({
      id: `operator_${Date.now()}`,
      speaker: "Operator",
      text: nextInstruction,
      timestamp: new Date().toISOString()
    });
    setInstruction("");
    setStatus("THINKING");

    if (!meetingId) {
      return;
    }

    try {
      await controls.sendInstruction(nextInstruction);
    } catch {
      setStatus(previousStatus);
    }
  }

  return (
    <Card className="h-[640px]">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>{botName} [LIVE]</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">Voice participant controls and instant steering.</p>
          </div>
          <Badge variant="success">{status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="rounded-2xl border border-border/70 bg-background/70 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">Status</p>
          <p className="mt-2 text-lg font-semibold">{status}</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Listening for wake word, meeting context, and typed operator instructions.
          </p>
        </div>

        <div className="space-y-3">
          <label className="text-sm font-medium">Ask your bot</label>
          <Input
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder="Tell Nova to summarize the last decision or answer the pricing question..."
          />
          <Button className="w-full" onClick={handleSendInstruction}>
            <SendHorizonal className="h-4 w-4" />
            Send
          </Button>
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <Button variant="outline" onClick={handleMuteToggle}>
            {status === "MUTED" ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
            {status === "MUTED" ? "Unmute" : "Mute"}
          </Button>
          <Button variant="secondary" onClick={handleStopSpeaking}>
            <Square className="h-4 w-4" />
            Stop
          </Button>
          <Button variant="destructive" onClick={handleLeave}>
            <PhoneOff className="h-4 w-4" />
            Leave Meeting
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              clearUnread();
              onOpenChat?.();
            }}
          >
            <MessageSquare className="h-4 w-4" />
            Chat
            {unreadCount > 0 ? (
              <span className="ml-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white">
                {unreadCount}
              </span>
            ) : null}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
