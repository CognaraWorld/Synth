"use client";

async function post(path: string, body?: unknown) {
  const response = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });

  if (!response.ok) {
    throw new Error("Live control request failed");
  }

  return response;
}

export function useLiveControls(meetingId: string) {
  return {
    mute: () => post(`/api/live-sessions/${meetingId}/mute`),
    unmute: () => post(`/api/live-sessions/${meetingId}/unmute`),
    stopSpeaking: () => post(`/api/live-sessions/${meetingId}/stop-speaking`),
    leave: () => post(`/api/live-sessions/${meetingId}/leave`),
    sendInstruction: (text: string) =>
      post(`/api/live-sessions/${meetingId}/instructions`, {
        instruction: text
      })
  };
}
