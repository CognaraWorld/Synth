"use client";

import { create } from "zustand";
import { TranscriptChunkDTO } from "@/types";

const MAX_CHUNKS_IN_STORE = 500;

interface TranscriptState {
  chunks: TranscriptChunkDTO[];
  status: "LISTENING" | "THINKING" | "SPEAKING" | "MUTED";
  highlightChunkId: string | null;
  addChunk: (chunk: TranscriptChunkDTO) => void;
  setStatus: (status: TranscriptState["status"]) => void;
  setHighlightChunkId: (id: string | null) => void;
  reset: () => void;
}

export const useTranscriptStore = create<TranscriptState>((set) => ({
  chunks: [],
  status: "LISTENING",
  highlightChunkId: null,
  addChunk: (chunk) =>
    set((state) => {
      const next =
        state.chunks.length >= MAX_CHUNKS_IN_STORE
          ? [...state.chunks.slice(1), chunk]
          : [...state.chunks, chunk];
      return { chunks: next };
    }),
  setStatus: (status) => set({ status }),
  setHighlightChunkId: (id) => set({ highlightChunkId: id }),
  reset: () => set({ chunks: [], status: "LISTENING", highlightChunkId: null })
}));
