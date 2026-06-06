"use client";

import React from "react";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export default function MessageBubble({ role, content, isStreaming = false }: MessageBubbleProps) {
  const isUser = role === "user";

  const renderContent = (text: string) => {
    const lines = text.split("\n");
    let inList = false;
    const listItems: string[] = [];
    const elements: React.ReactNode[] = [];

    const formatLine = (lineText: string, key: string) => {
      const parts = lineText.split(/(\*\*.*?\*\*|`.*?`)/);
      return parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={`${key}-${index}`} className="font-extrabold text-white">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={`${key}-${index}`} className="px-1.5 py-0.5 bg-zinc-950/80 text-indigo-400 rounded border border-zinc-800 text-xs font-mono font-semibold">
              {part.slice(1, -1)}
            </code>
          );
        }
        return part;
      });
    };

    lines.forEach((line, lineIdx) => {
      const trimmed = line.trim();
      const isListItem = trimmed.startsWith("- ") || trimmed.startsWith("* ");

      if (isListItem) {
        if (!inList) {
          inList = true;
        }
        listItems.push(trimmed.slice(2));
      } else {
        if (inList) {
          elements.push(
            <ul key={`list-${lineIdx}`} className="list-disc pl-5 my-2 space-y-1.5 text-zinc-300 text-sm">
              {listItems.map((item, itemIdx) => (
                <li key={`li-${lineIdx}-${itemIdx}`}>{formatLine(item, `li-${lineIdx}-${itemIdx}`)}</li>
              ))}
            </ul>
          );
          listItems.length = 0;
          inList = false;
        }

        if (trimmed === "") {
          elements.push(<div key={`space-${lineIdx}`} className="h-2" />);
        } else {
          elements.push(
            <p key={`p-${lineIdx}`} className="leading-relaxed text-sm text-zinc-200">
              {formatLine(line, `p-${lineIdx}`)}
            </p>
          );
        }
      }
    });

    if (inList && listItems.length > 0) {
      elements.push(
        <ul key="list-final" className="list-disc pl-5 my-2 space-y-1.5 text-zinc-300 text-sm">
          {listItems.map((item, itemIdx) => (
            <li key={`li-final-${itemIdx}`}>{formatLine(item, `li-final-${itemIdx}`)}</li>
          ))}
        </ul>
      );
    }

    return <div className="space-y-1">{elements}</div>;
  };

  return (
    <div className={`flex w-full gap-4 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/10 flex-shrink-0 text-white font-extrabold text-xs select-none">
          R
        </div>
      )}

      <div
        className={`max-w-[85%] sm:max-w-[70%] p-4 rounded-2xl border transition-all duration-200 relative group ${
          isUser
            ? "bg-zinc-900 border-zinc-800 text-white rounded-tr-none shadow-md shadow-zinc-950/20"
            : "bg-zinc-905 border-zinc-900 text-zinc-200 rounded-tl-none shadow-md shadow-zinc-950/20"
        }`}
      >
        {renderContent(content)}

        {isStreaming && (
          <span className="inline-flex ml-1 items-center">
            <span className="w-1.5 h-3.5 bg-indigo-400 animate-pulse" />
          </span>
        )}
      </div>

      {isUser && (
        <div className="h-8 w-8 rounded-lg bg-zinc-850 border border-zinc-750 flex items-center justify-center flex-shrink-0 text-zinc-300 font-extrabold text-xs select-none">
          U
        </div>
      )}
    </div>
  );
}
