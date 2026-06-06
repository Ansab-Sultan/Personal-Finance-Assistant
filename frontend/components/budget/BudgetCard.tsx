"use client";

import React from "react";

export interface BudgetStatus {
  id?: string;
  category: string;
  period: "monthly" | "yearly";
  spent: number;
  limit: number;
  remaining: number;
  ratio: number;
  state: "ok" | "warning" | "over";
}

interface BudgetCardProps {
  status: BudgetStatus;
  onEdit: (status: BudgetStatus) => void;
  onDelete: (category: string, period: string) => void;
}

export default function BudgetCard({ status, onEdit, onDelete }: BudgetCardProps) {
  const percentage = Math.min(100, Math.round(status.ratio * 100));
  
  const stateConfig = {
    ok: {
      color: "from-emerald-500 to-teal-500",
      text: "text-emerald-400",
      bg: "bg-emerald-500/10",
      border: "border-emerald-500/20",
      glow: "shadow-emerald-500/10",
      label: "On Track"
    },
    warning: {
      color: "from-amber-500 to-orange-500",
      text: "text-amber-400",
      bg: "bg-amber-500/10",
      border: "border-amber-500/20",
      glow: "shadow-amber-500/10",
      label: "Approaching Limit"
    },
    over: {
      color: "from-rose-500 to-red-500",
      text: "text-rose-400",
      bg: "bg-rose-500/10",
      border: "border-rose-500/20",
      glow: "shadow-rose-500/10",
      label: "Over Budget"
    }
  };

  const config = stateConfig[status.state] || stateConfig.ok;

  return (
    <div className={`p-6 bg-zinc-900/40 backdrop-blur-xl border border-zinc-800 rounded-2xl shadow-xl transition-all duration-300 hover:border-zinc-700 hover:shadow-2xl hover:translate-y-[-2px] flex flex-col justify-between h-52 relative overflow-hidden group`}>
      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${config.color} opacity-5 blur-2xl rounded-full transition-all duration-300 group-hover:opacity-10`} />
      
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-base font-bold text-white capitalize tracking-wide">
              {status.category}
            </h4>
            <span className="text-[10px] text-zinc-500 font-semibold uppercase tracking-wider">
              {status.period}
            </span>
          </div>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold ${config.bg} ${config.text} border ${config.border} shadow-sm`}>
            {config.label}
          </span>
        </div>

        <div className="flex items-baseline justify-between mb-4">
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-black font-mono text-white">
              ${status.spent.toFixed(2)}
            </span>
            <span className="text-zinc-500 text-xs font-medium">
              of ${status.limit.toFixed(2)}
            </span>
          </div>
          <span className="text-xs font-semibold text-zinc-400 font-mono">
            {percentage}%
          </span>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="w-full h-2 bg-zinc-950 rounded-full overflow-hidden border border-zinc-850 p-[1px]">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${config.color} shadow-lg ${config.glow} transition-all duration-500`}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <div className="flex justify-between items-center mt-2 text-[10px] text-zinc-500 font-semibold tracking-wide">
            <span>REMAINING</span>
            <span className={`font-mono text-xs ${status.state === "over" ? "text-rose-400" : "text-white"}`}>
              ${status.remaining.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <button
            onClick={() => onEdit(status)}
            className="px-2.5 py-1 bg-zinc-950 hover:bg-zinc-850 text-zinc-400 hover:text-white rounded-lg text-[10px] font-bold border border-zinc-850 transition-all"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(status.category, status.period)}
            className="px-2.5 py-1 bg-zinc-950 hover:bg-rose-950/30 text-zinc-400 hover:text-rose-400 rounded-lg text-[10px] font-bold border border-zinc-850 hover:border-rose-900/30 transition-all"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
