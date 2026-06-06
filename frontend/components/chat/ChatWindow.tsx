"use client";

import React, { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import { Message } from "../../lib/hooks/useChat";

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  onSuggestionClick: (suggestion: string) => void;
}

const SUGGESTIONS = [
  "What is my current budget status?",
  "How much did I spend on dining out this month?",
  "Show me my recent transactions.",
  "Check if I am close to any budget limits."
];

export default function ChatWindow({ messages, isLoading, error, onSuggestionClick }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-white border border-slate-200/80 rounded-2xl relative overflow-hidden shadow-sm">
      <div className="flex-1 overflow-y-auto p-6 space-y-6 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-xl mx-auto py-12">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-indigo-650 to-purple-650 flex items-center justify-center shadow-md shadow-indigo-500/10 mb-6">
              <span className="text-white font-extrabold text-2xl">P</span>
            </div>
            <h3 className="text-xl font-bold text-slate-900 tracking-tight">Meet Personal Finance Assistant</h3>
            <p className="text-xs text-slate-500 mt-2 max-w-sm leading-relaxed">
              Your premium personal finance assistant. Ask questions about your spending, budget configurations, or transactions.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8 w-full">
              {SUGGESTIONS.map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => onSuggestionClick(suggestion)}
                  className="p-3 bg-slate-50/50 border border-slate-200/80 hover:border-indigo-300 hover:bg-indigo-50/10 text-left rounded-xl transition-all duration-200 cursor-pointer"
                >
                  <p className="text-xs font-semibold text-slate-700 hover:text-indigo-950 line-clamp-2 leading-relaxed">{suggestion}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, index) => {
              const isLast = index === messages.length - 1;
              const isStreaming = isLast && msg.role === "assistant" && isLoading;
              return (
                <MessageBubble
                  key={index}
                  role={msg.role}
                  content={msg.content}
                  isStreaming={isStreaming}
                />
              );
            })}
            
            {isLoading && messages[messages.length - 1]?.role === "user" && (
              <div className="flex w-full gap-4 justify-start">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-600/10 flex-shrink-0 text-white font-extrabold text-xs">
                  R
                </div>
                <div className="p-4 bg-slate-50 border border-slate-200 text-slate-800 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            )}
          </>
        )}

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 text-rose-600 rounded-xl text-xs max-w-md mx-auto text-center font-medium shadow-2xs">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
