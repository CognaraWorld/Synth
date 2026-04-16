import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatSidebar } from "@/components/chat-sidebar";

const mocks = vi.hoisted(() => ({
  useChatMock: vi.fn(),
  useChatInsightsMock: vi.fn(),
  useVoiceInputMock: vi.fn(),
  useTranscriptStoreMock: vi.fn(),
}));

vi.mock("@/hooks/use-chat", () => ({
  useChat: mocks.useChatMock,
}));

vi.mock("@/hooks/use-chat-insights", () => ({
  useChatInsights: mocks.useChatInsightsMock,
}));

vi.mock("@/hooks/use-voice-input", () => ({
  useVoiceInput: mocks.useVoiceInputMock,
}));

vi.mock("@/stores/transcript-store", () => ({
  useTranscriptStore: mocks.useTranscriptStoreMock,
}));

type FetchMock = ReturnType<typeof vi.fn>;

function errorJsonResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ error: detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ChatSidebar", () => {
  let fetchMock: FetchMock;
  const sendMessageMock = vi.fn();
  const stopStreamingMock = vi.fn();
  const setHighlightChunkIdMock = vi.fn();

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    Element.prototype.scrollIntoView = vi.fn();

    mocks.useChatMock.mockReturnValue({
      messages: [],
      sendMessage: sendMessageMock,
      isLoading: false,
      isStreaming: false,
      error: null,
      stopStreaming: stopStreamingMock,
      suggestions: [],
      followUps: [],
    });
    mocks.useChatInsightsMock.mockReturnValue({ insights: [], unreadCount: 0, clearUnread: vi.fn() });
    mocks.useVoiceInputMock.mockReturnValue({
      isSupported: false,
      isListening: false,
      transcript: "",
      startListening: vi.fn(),
      stopListening: vi.fn(),
    });
    mocks.useTranscriptStoreMock.mockImplementation(
      (selector: (state: { chunks: unknown[]; setHighlightChunkId: typeof setHighlightChunkIdMock }) => unknown) =>
        selector({
          chunks: [],
          setHighlightChunkId: setHighlightChunkIdMock,
        }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    sendMessageMock.mockReset();
    stopStreamingMock.mockReset();
    setHighlightChunkIdMock.mockReset();
  });

  it("renders the empty-state prompt when there are no messages", () => {
    render(<ChatSidebar meetingId="meeting-1" isOpen onClose={vi.fn()} />);

    expect(screen.getByText("Ask anything about this meeting.")).toBeInTheDocument();
  });

  it("typing text and pressing Enter sends the message", async () => {
    const user = userEvent.setup();

    render(<ChatSidebar meetingId="meeting-1" isOpen onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText("Ask Cognara...");
    await user.type(input, "hello bot{enter}");

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledWith("hello bot");
    });
  });

  it("shows an export error banner when export fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(errorJsonResponse(500, "export failed"));
    mocks.useChatMock.mockReturnValue({
      messages: [
        {
          id: "msg-1",
          role: "assistant",
          content: "Existing message",
          createdAt: "2026-04-17T00:00:00.000Z",
          citations: null,
          toolCalls: null,
        },
      ],
      sendMessage: sendMessageMock,
      isLoading: false,
      isStreaming: false,
      error: null,
      stopStreaming: stopStreamingMock,
      suggestions: [],
      followUps: [],
    });

    render(<ChatSidebar meetingId="meeting-1" isOpen onClose={vi.fn()} />);

    await user.click(screen.getByTitle("Export as Markdown"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/chat/meeting-1/export");
    });
    expect(screen.getByText("Export failed. Please try again.")).toBeInTheDocument();
  });

  it("renders suggestions as clickable buttons", () => {
    mocks.useChatMock.mockReturnValue({
      messages: [],
      sendMessage: sendMessageMock,
      isLoading: false,
      isStreaming: false,
      error: null,
      stopStreaming: stopStreamingMock,
      suggestions: ["What were the key decisions?", "Summarize the action items"],
      followUps: [],
    });

    render(<ChatSidebar meetingId="meeting-1" isOpen onClose={vi.fn()} />);

    expect(screen.getByRole("button", { name: "What were the key decisions?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Summarize the action items" })).toBeInTheDocument();
  });

  it("shows Stop generating during streaming and calls stopStreaming when clicked", async () => {
    const user = userEvent.setup();
    mocks.useChatMock.mockReturnValue({
      messages: [
        {
          id: "msg-1",
          role: "assistant",
          content: "Streaming response",
          createdAt: "2026-04-17T00:00:00.000Z",
          citations: null,
          toolCalls: null,
        },
      ],
      sendMessage: sendMessageMock,
      isLoading: false,
      isStreaming: true,
      error: null,
      stopStreaming: stopStreamingMock,
      suggestions: [],
      followUps: [],
    });

    render(<ChatSidebar meetingId="meeting-1" isOpen onClose={vi.fn()} />);

    const stopButton = screen.getByRole("button", { name: "Stop generating" });
    expect(stopButton).toBeInTheDocument();

    await user.click(stopButton);

    expect(stopStreamingMock).toHaveBeenCalledTimes(1);
  });
});
