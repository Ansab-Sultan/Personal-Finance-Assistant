"use client";

import React, { useState } from "react";
import CsvUploader from "../../../components/transactions/CsvUploader";
import ReceiptScanner from "../../../components/transactions/ReceiptScanner";
import TransactionTable from "../../../components/transactions/TransactionTable";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../../lib/api";

/**
 * Main dashboard transaction page.
 */
export default function TransactionsPage() {
  const { getToken } = useAuth();
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [bankLoading, setBankLoading] = useState(false);

  const handleRefresh = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleSyncBank = async () => {
    setBankLoading(true);
    try {
      const token = await getToken();
      const res = await fetchWithAuth("/api/v1/transactions/fetch-bank?async=true", {
        method: "POST",
        token
      });
      
      const jobId = res.job_id;
      if (!jobId) {
        throw new Error("No job ID returned from server");
      }
      
      let attempts = 0;
      const maxAttempts = 30;
      
      const poll = async () => {
        if (attempts >= maxAttempts) {
          setBankLoading(false);
          return;
        }
        attempts++;
        try {
          const statusRes = await fetchWithAuth(`/api/v1/transactions/jobs/${jobId}`, {
            token
          });
          if (statusRes.status === "complete") {
            handleRefresh();
            setBankLoading(false);
          } else if (statusRes.status === "not_found") {
            setBankLoading(false);
          } else {
            setTimeout(poll, 1000);
          }
        } catch (err) {
          setBankLoading(false);
        }
      };
      
      setTimeout(poll, 1000);
    } catch (err) {
      setBankLoading(false);
    }
  };


  return (
    <div className="flex flex-col gap-8 text-slate-700">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Transactions</h1>
          <p className="text-sm text-slate-500 mt-1">Review, import, or manage your cash flow.</p>
        </div>
        <button
          onClick={handleSyncBank}
          disabled={bankLoading}
          className="px-4 py-2 bg-white hover:bg-slate-50 disabled:opacity-50 text-slate-750 font-medium rounded-xl text-xs border border-slate-200 transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 ${bankLoading ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.228 10H16.29" />
          </svg>
          {bankLoading ? "Syncing Bank..." : "Sync Mock Bank Feed"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        <div className="lg:col-span-2">
          <TransactionTable
            refreshTrigger={refreshTrigger}
            onRefresh={handleRefresh}
          />
        </div>
        <div className="space-y-8">
          <CsvUploader onUploadSuccess={handleRefresh} />
          <ReceiptScanner onSaveSuccess={handleRefresh} />
        </div>
      </div>
    </div>
  );
}
