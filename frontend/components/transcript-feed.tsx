"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRelativeDate } from "@/lib/utils";
import { useTranscriptStore } from "@/stores/transcript-store";

export function TranscriptFeed() {
  const chunks = useTranscriptStore((state) => state.chunks);
  const highlightChunkId = useTranscriptStore((state) => state.highlightChunkId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chunks.length]);

  useEffect(() => {
    if (!highlightChunkId) return;
    const highlighted = containerRef.current?.querySelector<HTMLElement>(`[data-chunk-id="${highlightChunkId}"]`);
    highlighted?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightChunkId]);

  return (
    <Card className="h-[640px]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Live transcript</CardTitle>
        <Badge variant="success">{chunks.length} events</Badge>
      </CardHeader>
      <CardContent className="h-[540px]">
        <ScrollArea className="h-full pr-4">
          <div ref={containerRef} className="space-y-4">
            {chunks.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                Waiting for transcript events from the live bot session.
              </div>
            ) : null}
            {chunks.map((chunk) => (
              <div
                key={chunk.id}
                data-chunk-id={chunk.id}
                className={`rounded-2xl border border-border/60 bg-background/70 p-4 transition-shadow ${
                  chunk.id === highlightChunkId ? "ring-2 ring-teal-500 ring-offset-1" : ""
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{chunk.speaker}</p>
                    {chunk.isBot ? <Badge>Bot</Badge> : null}
                  </div>
                  <span className="text-xs text-muted-foreground">{formatRelativeDate(chunk.timestamp)}</span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{chunk.text}</p>
              </div>
            ))}
            <div ref={scrollRef} />
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
