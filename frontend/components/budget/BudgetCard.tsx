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
      text: "text-emerald-700",
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      glow: "shadow-emerald-500/5",
      label: "On Track"
    },
    warning: {
      color: "from-amber-500 to-orange-500",
      text: "text-amber-700",
      bg: "bg-amber-50",
      border: "border-amber-200",
      glow: "shadow-amber-500/5",
      label: "Approaching Limit"
    },
    over: {
      color: "from-rose-500 to-red-500",
      text: "text-rose-700",
      bg: "bg-rose-50",
      border: "border-rose-200",
      glow: "shadow-rose-500/5",
      label: "Over Budget"
    }
  };

  const config = stateConfig[status.state] || stateConfig.ok;

  return (
    <div className={`p-6 bg-white border border-slate-200/80 rounded-2xl shadow-xs transition-all duration-300 hover:border-slate-300 hover:shadow-md hover:-translate-y-0.5 flex flex-col justify-between h-52 relative overflow-hidden group`}>
      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${config.color} opacity-[0.07] blur-2xl rounded-full transition-all duration-300 group-hover:opacity-[0.12] pointer-events-none`} />
      
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="text-base font-bold text-slate-900 capitalize tracking-wide">
              {status.category}
            </h4>
            <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
              {status.period}
            </span>
          </div>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold ${config.bg} ${config.text} border ${config.border} shadow-2xs`}>
            {config.label}
          </span>
        </div>

        <div className="flex items-baseline justify-between mb-4">
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-black font-mono text-slate-900">
              ${status.spent.toFixed(2)}
            </span>
            <span className="text-slate-500 text-xs font-medium">
              of ${status.limit.toFixed(2)}
            </span>
          </div>
          <span className="text-xs font-semibold text-slate-500 font-mono">
            {percentage}%
          </span>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200/60 p-[1px]">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${config.color} shadow-sm ${config.glow} transition-all duration-550`}
              style={{ width: `${percentage}%` }}
            />
          </div>
          <div className="flex justify-between items-center mt-2 text-[10px] text-slate-400 font-semibold tracking-wide">
            <span>REMAINING</span>
            <span className={`font-mono text-xs ${status.state === "over" ? "text-rose-600 font-bold" : "text-slate-900"}`}>
              ${status.remaining.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <button
            onClick={() => onEdit(status)}
            className="px-2.5 py-1 bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-slate-900 rounded-lg text-[10px] font-bold border border-slate-200 transition-all cursor-pointer"
          >
            Edit
          </button>
          <button
            onClick={() => onDelete(status.category, status.period)}
            className="px-2.5 py-1 bg-slate-50 hover:bg-rose-50 text-slate-650 hover:text-rose-600 rounded-lg text-[10px] font-bold border border-slate-200 hover:border-rose-250 transition-all cursor-pointer"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
