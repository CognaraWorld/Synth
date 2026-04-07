"use client";

import { formatRelativeDate } from "@/lib/utils";
import type { ChatMessage } from "@/lib/transformers/chat";

export function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`flex max-w-[85%] flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
        <div className={`flex items-end gap-2 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
          {!isUser ? (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-500 text-xs font-semibold text-white">
              C
            </div>
          ) : null}
          <div
            className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
              isUser ? "bg-[#2563EB] text-white" : "bg-muted text-foreground"
            }`}
          >
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
        <p className="px-1 text-xs text-muted-foreground">{formatRelativeDate(message.createdAt)}</p>
      </div>
    </div>
  );
}
