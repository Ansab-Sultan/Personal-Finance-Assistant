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
      
      const res = await fetchWithAuth("/api/v1/transactions/upload-csv?async=true", {
        method: "POST",
        body: formData,
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
          setError("CSV processing timed out.");
          setLoading(false);
          setDragActive(false);
          return;
        }
        attempts++;
        try {
          const statusRes = await fetchWithAuth(`/api/v1/transactions/jobs/${jobId}`, {
            token
          });
          if (statusRes.status === "complete") {
            setSummary(statusRes.result);
            onUploadSuccess();
            setLoading(false);
            setDragActive(false);
          } else if (statusRes.status === "not_found") {
            setError("Job failed or was not found.");
            setLoading(false);
            setDragActive(false);
          } else {
            setTimeout(poll, 1000);
          }
        } catch (err: any) {
          setError(err.message || "Failed to check upload status");
          setLoading(false);
          setDragActive(false);
        }
      };
      
      setTimeout(poll, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to upload file");
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
    <div className="w-full max-w-xl mx-auto p-6 bg-white border border-slate-200/80 rounded-2xl shadow-xs flex flex-col gap-4">
      <h2 className="text-lg font-bold text-slate-900 tracking-wide">Import Transaction CSV</h2>
      
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        className={`relative group border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-300 ${
          dragActive
            ? "border-indigo-500 bg-indigo-50/40 scale-[1.01]"
            : "border-slate-200 hover:border-slate-300 bg-slate-50/10"
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
          <div className="h-10 w-10 rounded-xl bg-white border border-slate-200 group-hover:border-slate-300 flex items-center justify-center text-indigo-600 group-hover:text-indigo-700 transition-colors shadow-2xs">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          </div>
          <p className="text-slate-700 text-sm font-medium">
            {loading ? "Processing transactions..." : "Drag and drop your CSV file here, or click to browse"}
          </p>
          <p className="text-slate-400 text-xs">Supports UTF-8 CSV exports from major banks</p>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-600 rounded-xl text-xs flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          {error}
        </div>
      )}

      {summary && (
        <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-xl flex flex-col gap-3 text-xs shadow-2xs">
          <h3 className="font-bold text-slate-900 text-sm">Upload Summary</h3>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-emerald-50 border border-emerald-100 rounded-lg">
              <p className="text-emerald-700 font-bold text-base">{summary.inserted}</p>
              <p className="text-slate-500 text-[10px] mt-0.5 font-medium">Inserted</p>
            </div>
            <div className="p-2 bg-amber-50 border border-amber-100 rounded-lg">
              <p className="text-amber-700 font-bold text-base">{summary.duplicates_skipped}</p>
              <p className="text-slate-500 text-[10px] mt-0.5 font-medium">Skipped</p>
            </div>
            <div className="p-2 bg-rose-50 border border-rose-100 rounded-lg">
              <p className="text-rose-700 font-bold text-base">{summary.quarantined_count}</p>
              <p className="text-slate-500 text-[10px] mt-0.5 font-medium">Quarantined</p>
            </div>
          </div>
          {summary.suspected_duplicates.length > 0 && (
            <div className="flex flex-col gap-1.5 border-t border-slate-200 pt-2">
              <p className="font-semibold text-amber-700">Suspected Near-Duplicates ({summary.suspected_duplicates.length})</p>
              <ul className="max-h-24 overflow-y-auto space-y-1 pr-1">
                {summary.suspected_duplicates.map((item, idx) => (
                  <li key={idx} className="flex justify-between text-[11px] text-slate-600 bg-white p-1.5 rounded-md border border-slate-200 shadow-2xs">
                    <span>{item.merchant} ({item.date})</span>
                    <span className="font-medium text-slate-900 font-bold font-mono">${item.amount}</span>
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
