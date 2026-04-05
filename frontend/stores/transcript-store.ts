"use client";

import { create } from "zustand";
import { TranscriptChunkDTO } from "@/types";

interface TranscriptState {
  chunks: TranscriptChunkDTO[];
  status: "LISTENING" | "THINKING" | "SPEAKING" | "MUTED";
  addChunk: (chunk: TranscriptChunkDTO) => void;
  setStatus: (status: TranscriptState["status"]) => void;
  reset: () => void;
}

export const useTranscriptStore = create<TranscriptState>((set) => ({
  chunks: [],
  status: "LISTENING",
  addChunk: (chunk) => set((state) => ({ chunks: [...state.chunks, chunk] })),
  setStatus: (status) => set({ status }),
  reset: () => set({ chunks: [], status: "LISTENING" })
}));
