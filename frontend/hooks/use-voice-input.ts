"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseVoiceInputReturn {
  isSupported: boolean;
  isListening: boolean;
  transcript: string;
  startListening: () => void;
  stopListening: () => void;
}

export function useVoiceInput(): UseVoiceInputReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  useEffect(() => {
    if (!isSupported) {
      return;
    }

    const SpeechRecognitionConstructor =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionConstructor) {
      return;
    }

    const recognition = new SpeechRecognitionConstructor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const results = event.results;
      const last = results[results.length - 1];
      setTranscript(last[0].transcript);
    };

    recognition.onspeechend = () => {
      recognition.stop();
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
      recognitionRef.current = null;
    };
  }, [isSupported]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current || isListening) {
      return;
    }
    setTranscript("");
    setIsListening(true);
    recognitionRef.current.start();
  }, [isListening]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) {
      return;
    }
    recognitionRef.current.stop();
    setIsListening(false);
  }, []);

  return { isSupported, isListening, transcript, startListening, stopListening };
}
