"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BotProfileDTO } from "@/types";

async function fetchBotProfile() {
  const response = await fetch("/api/bot-profile");
  if (!response.ok) {
    throw new Error("Failed to load bot profile");
  }

  const result = (await response.json()) as { data: BotProfileDTO };
  return result.data;
}

export function useBotProfile() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["bot-profile"],
    queryFn: fetchBotProfile
  });

  const mutation = useMutation({
    mutationFn: async (payload: Partial<BotProfileDTO>) => {
      const response = await fetch("/api/bot-profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("Failed to update bot profile");
      }

      const result = (await response.json()) as { data: BotProfileDTO };
      return result.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["bot-profile"], data);
    }
  });

  return { ...query, updateBotProfile: mutation.mutateAsync, isSaving: mutation.isPending };
}
