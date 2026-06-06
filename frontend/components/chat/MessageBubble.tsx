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
          return <strong key={`${key}-${index}`} className="font-extrabold text-slate-950">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={`${key}-${index}`} className="px-1.5 py-0.5 bg-slate-100/90 text-indigo-700 rounded border border-slate-200 text-xs font-mono font-semibold">
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
            <ul key={`list-${lineIdx}`} className="list-disc pl-5 my-2 space-y-1.5 text-slate-700 text-sm">
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
            <p key={`p-${lineIdx}`} className="leading-relaxed text-sm text-slate-800">
              {formatLine(line, `p-${lineIdx}`)}
            </p>
          );
        }
      }
    });

    if (inList && listItems.length > 0) {
      elements.push(
        <ul key="list-final" className="list-disc pl-5 my-2 space-y-1.5 text-slate-700 text-sm">
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
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-650 to-purple-650 flex items-center justify-center shadow-md shadow-indigo-500/10 flex-shrink-0 text-white font-extrabold text-xs select-none">
          R
        </div>
      )}

      <div
        className={`max-w-[85%] sm:max-w-[70%] p-4 rounded-2xl border transition-all duration-250 relative group ${
          isUser
            ? "bg-slate-100 border-slate-200/80 text-slate-800 rounded-tr-none shadow-2xs"
            : "bg-indigo-50/50 border-indigo-100/60 text-slate-800 rounded-tl-none shadow-2xs"
        }`}
      >
        {renderContent(content)}

        {isStreaming && (
          <span className="inline-flex ml-1 items-center">
            <span className="w-1.5 h-3.5 bg-indigo-500 animate-pulse" />
          </span>
        )}
      </div>

      {isUser && (
        <div className="h-8 w-8 rounded-lg bg-slate-250 border border-slate-350 flex items-center justify-center flex-shrink-0 text-slate-705 font-extrabold text-xs select-none">
          U
        </div>
      )}
    </div>
  );
}
