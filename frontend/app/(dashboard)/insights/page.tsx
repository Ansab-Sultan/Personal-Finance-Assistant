"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../../lib/api";

interface Subscription {
  id: string;
  merchant: string;
  amount: number;
  cadence_days: number;
  last_seen: string;
  confidence: number;
}

interface Anomaly {
  id: string;
  transaction_id: string;
  category: string;
  amount: number;
  reason: string;
  detected_at: string;
}

/**
 * Insights page — read-only feeds for precomputed recurring subscriptions and flagged anomalies.
 * Pure structured UI actions: each hits its REST endpoint directly, no chat agent involved.
 */
export default function InsightsPage() {
  const { getToken } = useAuth();
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const token = await getToken();
        const [subs, anoms] = await Promise.all([
          fetchWithAuth("/api/v1/transactions/subscriptions", { token }),
          fetchWithAuth("/api/v1/transactions/anomalies", { token }),
        ]);
        setSubscriptions(subs || []);
        setAnomalies(anoms || []);
      } catch (err) {
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Insights</h1>
        <p className="text-xs text-slate-500 mt-1">Recurring subscriptions and unusual activity, detected from your transactions.</p>
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400 font-medium text-sm">Loading insights...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          {/* Recurring subscriptions */}
          <section className="bg-white border border-slate-200/80 rounded-2xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
              <div className="p-1.5 bg-indigo-50 rounded-lg text-indigo-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.228 10H16.29M20 20v-5h-.581m-15.357-2a8.003 8.003 0 0015.357 2H7.71" />
                </svg>
              </div>
              <h2 className="text-sm font-bold text-slate-900">Recurring Subscriptions</h2>
              <span className="ml-auto text-[10px] font-semibold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{subscriptions.length}</span>
            </div>

            {subscriptions.length === 0 ? (
              <div className="py-14 text-center text-xs text-slate-400">No recurring subscriptions detected yet.</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {subscriptions.map((s) => (
                  <li key={s.id} className="px-5 py-3.5 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900 truncate">{s.merchant}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        ~every {s.cadence_days} days · last seen {s.last_seen}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-bold text-slate-900">${Math.abs(s.amount).toFixed(2)}</p>
                      <p className="text-[10px] text-slate-400">{(s.confidence * 100).toFixed(0)}% confidence</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Flagged anomalies */}
          <section className="bg-white border border-slate-200/80 rounded-2xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
              <div className="p-1.5 bg-rose-50 rounded-lg text-rose-600">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h2 className="text-sm font-bold text-slate-900">Unusual Activity</h2>
              <span className="ml-auto text-[10px] font-semibold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{anomalies.length}</span>
            </div>

            {anomalies.length === 0 ? (
              <div className="py-14 text-center text-xs text-slate-400">No unusual activity flagged.</div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {anomalies.map((a) => (
                  <li key={a.id} className="px-5 py-3.5 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-800 capitalize">{a.category}</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">{a.reason}</p>
                      <p className="text-[10px] text-slate-300 mt-0.5">{new Date(a.detected_at).toLocaleDateString()}</p>
                    </div>
                    <p className="text-sm font-bold text-rose-600 flex-shrink-0">${Math.abs(a.amount).toFixed(2)}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
