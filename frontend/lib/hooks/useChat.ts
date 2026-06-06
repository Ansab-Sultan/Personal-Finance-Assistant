"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../api";

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function useChat() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const history = await fetchWithAuth("/api/v1/chat/history", { token });
      setMessages(history || []);
    } catch (err: any) {
      setError(err.message || "Failed to load chat history");
    }
  }, [getToken]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    setError(null);
    setIsLoading(true);

    const userMessage: Message = {
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, userMessage]);

    try {
      const token = await getToken();
      const response = await fetch(`${BACKEND_URL}/api/v1/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ message: trimmed })
      });

      if (!response.ok) {
        let errMsg = "Failed to send message";
        try {
          const errData = await response.json();
          errMsg = errData.detail || errMsg;
        } catch {}
        throw new Error(errMsg);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Response body is not readable");
      }

      const decoder = new TextDecoder();
      let done = false;
      let assistantReply = "";

      const assistantPlaceholder: Message = {
        role: "assistant",
        content: "",
        created_at: new Date().toISOString()
      };

      setMessages((prev) => [...prev, assistantPlaceholder]);

      let buffer = "";
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: !doneReading });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const cleaned = line.trim();
            if (cleaned.startsWith("data: ")) {
              const tokenValue = cleaned.slice(6);
              assistantReply += tokenValue;
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  last.content = assistantReply;
                }
                return updated;
              });
            }
          }
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to send message");
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  const clearMessages = useCallback(async () => {
    try {
      const token = await getToken();
      await fetchWithAuth("/api/v1/chat/history", { method: "DELETE", token });
    } catch {
    } finally {
      setMessages([]);
      setError(null);
    }
  }, [getToken]);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    reloadHistory: fetchHistory
  };
}
