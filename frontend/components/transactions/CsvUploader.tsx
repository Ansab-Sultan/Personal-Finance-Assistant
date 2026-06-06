"use client";

import React, { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../lib/api";

interface CsvUploaderProps {
  onUploadSuccess: () => void;
}

interface UploadSummary {
  inserted: number;
  duplicates_skipped: number;
  quarantined_count: number;
  quarantined_items: any[];
  suspected_duplicates: any[];
}

/**
 * Premium drag-and-drop CSV Uploader component.
 */
export default function CsvUploader({ onUploadSuccess }: CsvUploaderProps) {
  const { getToken } = useAuth();
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<UploadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const uploadFile = async (file: File) => {
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const token = await getToken();
      const formData = new FormData();
      formData.append("file", file);
      
      const res = await fetchWithAuth("/api/v1/transactions/upload-csv?async=false", {
        method: "POST",
        body: formData,
        token
      });
      
      setSummary(res);
      onUploadSuccess();
    } catch (err: any) {
      setError(err.message || "Failed to upload file");
    } finally {
      setLoading(false);
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      uploadFile(e.target.files[0]);
    }
  };

  return (
    <div className="w-full max-w-xl mx-auto p-6 bg-zinc-905 border border-zinc-800 rounded-2xl shadow-xl flex flex-col gap-4">
      <h2 className="text-lg font-bold text-white tracking-wide">Import Transaction CSV</h2>
      
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`relative group border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 ${
          dragActive
            ? "border-indigo-500 bg-indigo-500/10 scale-102"
            : "border-zinc-800 hover:border-zinc-700 bg-zinc-950/20"
        }`}
      >
        <input
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={loading}
        />
        <div className="flex flex-col items-center gap-2">
          <div className="h-10 w-10 rounded-xl bg-zinc-900 border border-zinc-800 group-hover:border-zinc-700 flex items-center justify-center text-indigo-400 group-hover:text-indigo-300 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          </div>
          <p className="text-zinc-300 text-sm font-medium">
            {loading ? "Processing transactions..." : "Drag and drop your CSV file here, or click to browse"}
          </p>
          <p className="text-zinc-500 text-xs">Supports UTF-8 CSV exports from major banks</p>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-950/30 border border-red-800 text-red-400 rounded-xl text-xs flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          {error}
        </div>
      )}

      {summary && (
        <div className="p-4 bg-zinc-950 border border-zinc-800 rounded-xl flex flex-col gap-3 text-xs">
          <h3 className="font-bold text-white text-sm">Upload Summary</h3>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-emerald-950/20 border border-emerald-900/30 rounded-lg">
              <p className="text-emerald-400 font-bold text-base">{summary.inserted}</p>
              <p className="text-zinc-400 text-[10px] mt-0.5">Inserted</p>
            </div>
            <div className="p-2 bg-amber-950/20 border border-amber-900/30 rounded-lg">
              <p className="text-amber-400 font-bold text-base">{summary.duplicates_skipped}</p>
              <p className="text-zinc-400 text-[10px] mt-0.5">Skipped</p>
            </div>
            <div className="p-2 bg-rose-950/20 border border-rose-900/30 rounded-lg">
              <p className="text-rose-400 font-bold text-base">{summary.quarantined_count}</p>
              <p className="text-zinc-400 text-[10px] mt-0.5">Quarantined</p>
            </div>
          </div>
          {summary.suspected_duplicates.length > 0 && (
            <div className="flex flex-col gap-1.5 border-t border-zinc-800/80 pt-2">
              <p className="font-semibold text-amber-400">Suspected Near-Duplicates ({summary.suspected_duplicates.length})</p>
              <ul className="max-h-24 overflow-y-auto space-y-1 pr-1">
                {summary.suspected_duplicates.map((item, idx) => (
                  <li key={idx} className="flex justify-between text-[11px] text-zinc-400 bg-zinc-900/50 p-1.5 rounded-md border border-zinc-800">
                    <span>{item.merchant} ({item.date})</span>
                    <span className="font-medium text-white">${item.amount}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
