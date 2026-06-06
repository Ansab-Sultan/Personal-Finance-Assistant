"use client";

import React, { useState } from "react";
import ChatWindow from "../../../components/chat/ChatWindow";
import ReceiptUpload from "../../../components/chat/ReceiptUpload";
import { useChat } from "../../../lib/hooks/useChat";

export default function ChatPage() {
  const { messages, isLoading, error, sendMessage, clearMessages } = useChat();
  const [input, setInput] = useState("");
  const [attachedReceipt, setAttachedReceipt] = useState<{ base64: string; name: string } | null>(null);

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    
    let textToSend = input.trim();
    if (!textToSend && !attachedReceipt) return;

    if (attachedReceipt) {
      const receiptAnnotation = `[Uploaded Receipt: ${attachedReceipt.name}]`;
      textToSend = textToSend ? `${receiptAnnotation} ${textToSend}` : receiptAnnotation;
      setAttachedReceipt(null);
    }

    sendMessage(textToSend);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion);
  };

  const handleReceiptUpload = (base64: string, name: string) => {
    setAttachedReceipt({ base64, name });
  };

  const handleReceiptClear = () => {
    setAttachedReceipt(null);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">AI Assistant</h1>
          <p className="text-xs text-slate-500 mt-1">Chat with Personal Finance Assistant to gain deep insights into your cash flow and budgets.</p>
        </div>
        <button
          onClick={clearMessages}
          className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-slate-900 text-xs font-semibold rounded-xl border border-slate-200 transition-all flex items-center gap-1.5 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Clear Thread
        </button>
      </div>

      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        error={error}
        onSuggestionClick={handleSuggestionClick}
      />

      <div className="space-y-3 bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row gap-4 items-end">
          <div className="w-full sm:w-80 flex-shrink-0">
            <ReceiptUpload onUpload={handleReceiptUpload} onClear={handleReceiptClear} />
          </div>

          <form onSubmit={handleSend} className="flex-1 w-full flex gap-3 items-end">
            <div className="flex-1 bg-slate-50 border border-slate-200 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 rounded-xl px-3 py-2 transition-all flex items-end">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={attachedReceipt ? "Add a message about this receipt..." : "Ask Personal Finance Assistant anything..."}
                rows={1}
                className="flex-1 bg-transparent text-slate-900 text-sm outline-none resize-none placeholder-slate-450 max-h-24 min-h-[1.5rem] py-0.5 leading-relaxed"
                style={{ height: "auto" }}
              />
            </div>
            <button
              type="submit"
              disabled={isLoading || (!input.trim() && !attachedReceipt)}
              className="h-10 w-10 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-650 hover:opacity-95 text-white font-bold rounded-xl flex items-center justify-center transition-all shadow-md shadow-indigo-600/10 flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 transform rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
