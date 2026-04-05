"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useChat } from "@/hooks/use-chat";
import { ChatMessageBubble } from "@/components/chat-message";

interface ChatSidebarProps {
  meetingId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function ChatSidebar({ meetingId, isOpen, onClose }: ChatSidebarProps) {
  const { messages, sendMessage, isLoading } = useChat(meetingId);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  function handleSend() {
    if (!input.trim()) return;
    sendMessage(input);
    setInput("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-[400px] p-0 sm:w-[440px]">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle>Chat with Cognara</SheetTitle>
        </SheetHeader>
        <ScrollArea className="flex-1 px-4 py-4">
          <div className="space-y-4">
            {messages.length === 0 && !isLoading ? (
              <p className="py-8 text-center text-sm text-muted-foreground">Ask anything about this meeting.</p>
            ) : null}
            {messages.map((message) => (
              <ChatMessageBubble key={message.id} message={message} />
            ))}
            {isLoading ? (
              <div className="flex items-center gap-1.5 px-3 py-2">
                <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
              </div>
            ) : null}
            <div ref={scrollRef} />
          </div>
        </ScrollArea>
        <div className="flex gap-2 border-t px-4 py-3">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Cognara..."
            disabled={isLoading}
          />
          <Button onClick={handleSend} disabled={isLoading || !input.trim()}>
            Send
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
