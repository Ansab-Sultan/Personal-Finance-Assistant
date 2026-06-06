"use client";

import React, { useState, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../lib/api";

interface ReceiptScannerProps {
  onSaveSuccess: () => void;
}

interface ParsedReceipt {
  merchant: string;
  amount: number;
  date: string;
  currency: string;
  confidence: number;
}

/**
 * Deterministic REST receipt path (no chat agent): upload an image → POST /receipts/parse
 * (Gemini vision) → review/edit the extracted fields → POST /transactions to record it.
 */
export default function ReceiptScanner({ onSaveSuccess }: ReceiptScannerProps) {
  const { getToken } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [stage, setStage] = useState<"idle" | "parsing" | "confirm" | "saving">("idle");
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [category, setCategory] = useState("uncategorized");
  const [confidence, setConfidence] = useState<number | null>(null);

  const reset = () => {
    setStage("idle");
    setError(null);
    setConflict(false);
    setConfidence(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFile = (file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }
    setError(null);
    setStage("parsing");

    const reader = new FileReader();
    reader.onload = async () => {
      if (typeof reader.result !== "string") return;
      try {
        const token = await getToken();
        const parsed: ParsedReceipt = await fetchWithAuth("/api/v1/transactions/receipts/parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_base64: reader.result, mime_type: file.type }),
          token,
        });
        setMerchant(parsed.merchant || "");
        setAmount(parsed.amount != null ? String(Math.abs(parsed.amount)) : "");
        setDate(parsed.date || "");
        setCurrency(parsed.currency || "USD");
        setConfidence(parsed.confidence ?? null);
        setStage("confirm");
      } catch (err: any) {
        setError(err.message || "Could not read that receipt. Try a clearer image.");
        setStage("idle");
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async (force: boolean = false) => {
    setStage("saving");
    setError(null);
    if (!force) setConflict(false);

    try {
      const token = await getToken();
      const parsedAmount = Math.abs(parseFloat(amount));
      const isCredit = category === "income" || category === "transfer";
      const payload = {
        date,
        amount: isCredit ? parsedAmount : -parsedAmount,
        currency,
        merchant,
        raw_description: merchant,
        category,
        source: "receipt",
      };
      await fetchWithAuth(`/api/v1/transactions?force=${force}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        token,
      });
      reset();
      onSaveSuccess();
    } catch (err: any) {
      if (err.status === 409) {
        setConflict(true);
      } else {
        setError(err.message || "Failed to save the transaction.");
      }
      setStage("confirm");
    }
  };

  const lowConfidence = confidence != null && confidence < 0.6;

  return (
    <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="p-1.5 bg-indigo-50 rounded-lg text-indigo-600">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <h3 className="text-sm font-bold text-slate-900">Scan a Receipt</h3>
      </div>
      <p className="text-xs text-slate-500 mb-4">Extract a transaction from a photo, then review before saving.</p>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-100 text-rose-600 rounded-xl text-xs mb-4">{error}</div>
      )}

      {stage === "idle" && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border border-dashed border-slate-200 hover:border-indigo-400 rounded-xl p-6 text-center cursor-pointer transition-all bg-slate-50/30 hover:bg-indigo-500/5"
        >
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
          <p className="text-xs font-semibold text-slate-700">Upload Receipt Image</p>
          <p className="text-[10px] text-slate-400 mt-0.5">Click to choose a photo</p>
        </div>
      )}

      {stage === "parsing" && (
        <div className="py-8 text-center text-slate-400 text-sm font-medium flex items-center justify-center gap-2">
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.228 10H16.29" />
          </svg>
          Reading receipt...
        </div>
      )}

      {(stage === "confirm" || stage === "saving") && (
        <div className="space-y-3">
          {confidence != null && (
            <div className={`text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full inline-block ${
              lowConfidence ? "bg-amber-50 text-amber-700 border border-amber-200" : "bg-emerald-50 text-emerald-700 border border-emerald-200"
            }`}>
              {lowConfidence ? "Low confidence — please verify" : "Parsed"} · {(confidence * 100).toFixed(0)}%
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Date</label>
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all" />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Amount</label>
              <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all" />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Merchant</label>
            <input type="text" value={merchant} onChange={(e) => setMerchant(e.target.value)}
              className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Currency</label>
              <input type="text" maxLength={3} value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm uppercase focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all" />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Category</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-white border border-slate-200 text-slate-850 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer">
                <option value="groceries">Groceries</option>
                <option value="restaurants">Restaurants</option>
                <option value="transport">Transport / Travel</option>
                <option value="fuel">Fuel</option>
                <option value="utilities">Utilities</option>
                <option value="rent">Rent / Housing</option>
                <option value="health">Health / Medical</option>
                <option value="entertainment">Entertainment</option>
                <option value="shopping">Shopping</option>
                <option value="subscriptions">Subscriptions</option>
                <option value="travel">Travel</option>
                <option value="education">Education</option>
                <option value="income">Income / Salary</option>
                <option value="transfer">Transfer</option>
                <option value="uncategorized">Uncategorized</option>
              </select>
            </div>
          </div>

          {conflict && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs space-y-2">
              <p className="text-amber-700 font-semibold">A matching transaction already exists.</p>
              <div className="flex gap-2">
                <button type="button" onClick={() => handleSave(true)}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-lg transition-all cursor-pointer">
                  Save anyway
                </button>
                <button type="button" onClick={() => setConflict(false)}
                  className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 rounded-lg border border-slate-200 transition-all cursor-pointer">
                  Cancel
                </button>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={reset}
              className="px-4 py-2 bg-slate-50 hover:bg-slate-100 text-slate-650 font-medium rounded-xl border border-slate-200 transition-all text-xs cursor-pointer">
              Discard
            </button>
            <button type="button" disabled={stage === "saving" || conflict} onClick={() => handleSave(false)}
              className="px-4 py-2 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-650 hover:opacity-95 text-white font-medium rounded-xl transition-all shadow-md shadow-indigo-600/10 text-xs disabled:opacity-50 cursor-pointer">
              {stage === "saving" ? "Saving..." : "Save Transaction"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
