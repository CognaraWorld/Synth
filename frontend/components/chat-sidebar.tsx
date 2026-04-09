"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Download, Lightbulb, Mic, MicOff, Square } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useChat } from "@/hooks/use-chat";
import { useChatInsights } from "@/hooks/use-chat-insights";
import { useVoiceInput } from "@/hooks/use-voice-input";
import { ChatMessageBubble } from "@/components/chat-message";
import { useTranscriptStore } from "@/stores/transcript-store";

interface ChatSidebarProps {
  meetingId: string;
  isOpen: boolean;
  onClose: () => void;
  crossMeeting?: boolean;
}

export function ChatSidebar({ meetingId, isOpen, onClose, crossMeeting }: ChatSidebarProps) {
  const { messages, sendMessage, isLoading, isStreaming, error, stopStreaming, suggestions, followUps } = useChat(meetingId, { crossMeeting });
  const { insights } = useChatInsights(crossMeeting ? undefined : meetingId, isOpen && !crossMeeting);
  const { isSupported: voiceSupported, isListening, transcript: voiceTranscript, startListening, stopListening } = useVoiceInput();
  const [input, setInput] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chunks = useTranscriptStore((state) => state.chunks);
  const setHighlightChunkId = useTranscriptStore((state) => state.setHighlightChunkId);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [insights.length, isLoading, messages.length]);

  useEffect(() => {
    if (voiceTranscript) {
      setInput(voiceTranscript);
    }
  }, [voiceTranscript]);

  useEffect(() => {
    return () => {
      if (highlightTimerRef.current) {
        clearTimeout(highlightTimerRef.current);
      }
    };
  }, []);

  function parseCitationSeconds(value: string) {
    const parts = value.split(":").map((part) => parseInt(part, 10));
    if (parts.some(Number.isNaN) || parts.length !== 2) return null;
    return parts[0] * 60 + parts[1];
  }

  function handleCitationClick(citation: { type: string; timestamp?: string }) {
    if (citation.type !== "transcript" || !citation.timestamp || chunks.length === 0) {
      return;
    }

    const targetSeconds = parseCitationSeconds(citation.timestamp);
    const firstChunkMs = Date.parse(chunks[0]?.timestamp ?? "");
    if (targetSeconds === null || Number.isNaN(firstChunkMs)) {
      return;
    }

    let closestChunkId: string | null = null;
    let closestDistance = Number.POSITIVE_INFINITY;

    for (const chunk of chunks) {
      const chunkMs = Date.parse(chunk.timestamp);
      if (Number.isNaN(chunkMs)) continue;
      const relativeSeconds = Math.max(0, Math.round((chunkMs - firstChunkMs) / 1000));
      const distance = Math.abs(relativeSeconds - targetSeconds);
      if (distance < closestDistance) {
        closestDistance = distance;
        closestChunkId = chunk.id;
      }
    }

    if (!closestChunkId) return;

    setHighlightChunkId(closestChunkId);
    if (highlightTimerRef.current) {
      clearTimeout(highlightTimerRef.current);
    }
    highlightTimerRef.current = setTimeout(() => setHighlightChunkId(null), 3000);
  }

  function handleSend() {
    if (!input.trim()) return;
    void sendMessage(input);
    setInput("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  async function handleExport() {
    if (isExporting) return;
    setIsExporting(true);
    try {
      const response = await fetch(`/api/chat/${meetingId}/export`);
      if (!response.ok) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "chat-export.md";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      // Download failed — user can retry
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="flex h-full w-[400px] flex-col p-0 sm:w-[440px]">
        <SheetHeader className="flex flex-row items-center justify-between space-y-0 border-b px-6 py-4">
          <SheetTitle>{crossMeeting ? "Chat across meetings" : "Chat with Cognara"}</SheetTitle>
          {messages.length > 0 && !crossMeeting ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={handleExport}
              disabled={isExporting}
              title="Export as Markdown"
            >
              <Download className="h-4 w-4" />
            </Button>
          ) : null}
        </SheetHeader>
        <ScrollArea className="flex-1 px-4 py-4">
          <div className="space-y-4">
            {messages.length === 0 && !isLoading ? (
              suggestions.length > 0 ? (
                <div className="space-y-3 py-4">
                  <p className="text-center text-sm text-muted-foreground">
                    {crossMeeting ? "Try asking:" : "Suggested questions:"}
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {suggestions.map((suggestion, index) => (
                      <Button
                        key={index}
                        variant="outline"
                        size="sm"
                        className="h-auto whitespace-normal rounded-full px-3 py-1.5 text-xs"
                        onClick={() => void sendMessage(suggestion)}
                      >
                        {suggestion}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  {crossMeeting
                    ? "Ask about trends, compare decisions across meetings..."
                    : "Ask anything about this meeting."}
                </p>
              )
            ) : null}
            {messages.map((message, index) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                isStreaming={isStreaming && index === messages.length - 1 && message.role === "assistant"}
                onCitationClick={handleCitationClick}
              />
            ))}
            {insights.length > 0
              ? insights.map((insight, index) => (
                  <div
                    key={`insight-${index}`}
                    className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2"
                  >
                    <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                    <div className="text-xs">
                      <p className="font-medium text-amber-800">Fact check: {insight.speaker}</p>
                      <p className="text-amber-700">Claim: {insight.claim}</p>
                      <p className="text-amber-900">Correction: {insight.correction}</p>
                    </div>
                  </div>
                ))
              : null}
            {isLoading && !isStreaming ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">
                Thinking...
              </div>
            ) : null}
            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            ) : null}
            <div ref={scrollRef} />
          </div>
        </ScrollArea>
        {followUps.length > 0 && !isLoading && !isStreaming ? (
          <div className="border-t px-4 py-2">
            <div className="flex flex-wrap gap-1.5">
              {followUps.map((followUp, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  className="h-auto whitespace-normal rounded-full px-3 py-1.5 text-xs"
                  onClick={() => void sendMessage(followUp)}
                >
                  {followUp}
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        {isStreaming ? (
          <div className="border-t px-4 py-3">
            <Button variant="outline" size="sm" onClick={stopStreaming} className="w-full">
              <Square className="h-3 w-3" />
              Stop generating
            </Button>
          </div>
        ) : null}
        <div className="flex gap-2 border-t px-4 py-3">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={crossMeeting ? "Compare decisions, ask about trends..." : "Ask Cognara..."}
            disabled={isLoading}
          />
          {voiceSupported ? (
            <Button
              variant={isListening ? "destructive" : "outline"}
              size="icon"
              onClick={isListening ? stopListening : startListening}
              disabled={isLoading || isStreaming}
              className={isListening ? "animate-pulse" : ""}
              title={isListening ? "Stop listening" : "Voice input"}
            >
              {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </Button>
          ) : null}
          <Button onClick={handleSend} disabled={isLoading || isStreaming || !input.trim()}>
            Send
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
