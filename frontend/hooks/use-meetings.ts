"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MeetingDTO } from "@/types";

async function fetchMeetings() {
  const response = await fetch("/api/meetings");
  if (!response.ok) {
    throw new Error("Failed to load meetings");
  }

  const result = (await response.json()) as { data: MeetingDTO[] };
  return result.data;
}

export function useMeetings() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["meetings"],
    queryFn: fetchMeetings
  });

  const createMutation = useMutation({
    mutationFn: async (payload: { joinUrl: string; title?: string; scheduledTime?: string }) => {
      const response = await fetch("/api/meetings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("Failed to create meeting");
      }

      const result = (await response.json()) as { data: MeetingDTO };
      return result.data;
    },
    onSuccess: (meeting) => {
      queryClient.setQueryData<MeetingDTO[]>(["meetings"], (current = []) => [meeting, ...current]);
    }
  });

  return {
    ...query,
    createMeeting: createMutation.mutateAsync,
    isCreating: createMutation.isPending
  };
}
