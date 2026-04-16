"use client";

import { useState, type ReactNode } from "react";
import { CheckSquare, ChevronDown, ChevronRight, FileText, Globe } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatRelativeDate } from "@/lib/utils";
import type { CitationReference, ChatMessage, ToolCallInfo } from "@/lib/transformers/chat";

type CitationClickHandler = (citation: {
  type: CitationReference["type"];
  timestamp?: string;
  filename?: string;
  page?: number;
}) => void;

function renderContent(content: string, onCitationClick?: CitationClickHandler): ReactNode[] | string {
  const parts: ReactNode[] = [];
  const regex = /\[T:(\d{1,3}:\d{2})\]|\[D:([^:\]]+):(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }

    if (match[1]) {
      const timestamp = match[1];
      parts.push(
        <Badge
          key={match.index}
          variant="secondary"
          className="mx-0.5 cursor-pointer border-teal-300 bg-teal-50 px-1.5 py-0 text-[10px] font-medium text-teal-700 hover:bg-teal-100"
          onClick={() => onCitationClick?.({ type: "transcript", timestamp })}
        >
          {timestamp}
        </Badge>
      );
    } else if (match[2] && match[3]) {
      const filename = match[2].trim();
      const page = parseInt(match[3], 10);
      parts.push(
        <Badge
          key={match.index}
          variant="secondary"
          className="mx-0.5 cursor-pointer border-blue-300 bg-blue-50 px-1.5 py-0 text-[10px] font-medium text-blue-700 hover:bg-blue-100"
          onClick={() => onCitationClick?.({ type: "document", filename, page })}
        >
          {filename} p.{page}
        </Badge>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return parts.length > 0 ? parts : content;
}

function ToolCallsSection({ toolCalls }: { toolCalls: ToolCallInfo[] }) {
  const [expanded, setExpanded] = useState(false);

  const iconMap: Record<string, ReactNode> = {
    web_search: <Globe className="h-3 w-3" />,
    document_lookup: <FileText className="h-3 w-3" />,
    create_action_item: <CheckSquare className="h-3 w-3" />,
  };

  return (
    <div className="mt-2 border-t border-border/50 pt-2">
      <button
        onClick={() => setExpanded((current) => !current)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
        type="button"
      >
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {toolCalls.length} tool{toolCalls.length > 1 ? "s" : ""} used
      </button>
      {expanded ? (
        <div className="mt-1.5 space-y-1.5">
          {toolCalls.map((toolCall, index) => (
            <div key={index} className="flex items-start gap-1.5 rounded bg-muted/50 px-2 py-1 text-[10px]">
              <span className="mt-0.5 shrink-0">
                {iconMap[toolCall.tool_name] ?? <Globe className="h-3 w-3" />}
              </span>
              <div>
                <span className="font-medium">{toolCall.tool_name.replace(/_/g, " ")}</span>
                <span className="text-muted-foreground"> {toolCall.output_summary}</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function ChatMessageBubble({
  message,
  isStreaming = false,
  onCitationClick,
}: {
  message: ChatMessage;
  isStreaming?: boolean;
  onCitationClick?: CitationClickHandler;
}) {
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
            <p className="whitespace-pre-wrap">
              {renderContent(message.content, onCitationClick)}
              {isStreaming ? <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-current align-middle" /> : null}
            </p>
            {!isUser && message.toolCalls && message.toolCalls.length > 0 ? (
              <ToolCallsSection toolCalls={message.toolCalls} />
            ) : null}
          </div>
        </div>
        <p className="px-1 text-xs text-muted-foreground">{formatRelativeDate(message.createdAt)}</p>
      </div>
    </div>
  );
}
