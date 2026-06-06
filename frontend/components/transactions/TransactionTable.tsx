"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../lib/api";
import { formatMoney } from "../../lib/format";
import TransactionForm from "./TransactionForm";

interface Transaction {
  id: string;
  date: string;
  amount: number;
  currency: string;
  merchant: string;
  raw_description: string;
  category: string;
  source: string;
}

interface TransactionTableProps {
  refreshTrigger: number;
  onRefresh: () => void;
}

/**
 * Premium transaction ledger component with live filtering, pagination, and inline editing.
 */
export default function TransactionTable({ refreshTrigger, onRefresh }: TransactionTableProps) {
  const { getToken } = useAuth();
  
  const [items, setItems] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size] = useState(15);
  
  const [category, setCategory] = useState("");
  const [merchantSearch, setMerchantSearch] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const loadTransactions = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      
      let query = `/api/v1/transactions?page=${page}&size=${size}`;
      if (category) {
        query += `&category=${category}`;
      }
      if (merchantSearch) {
        query += `&merchant=${encodeURIComponent(merchantSearch)}`;
      }
      if (startDate) {
        query += `&start_date=${startDate}`;
      }
      if (endDate) {
        query += `&end_date=${endDate}`;
      }
      
      const res = await fetchWithAuth(query, { token });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
  }, [page, category, startDate, endDate, refreshTrigger]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadTransactions();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this transaction?")) {
      return;
    }
    try {
      const token = await getToken();
      await fetchWithAuth(`/api/v1/transactions/${id}`, {
        method: "DELETE",
        token
      });
      onRefresh();
    } catch (err) {
    }
  };

  const totalPages = Math.ceil(total / size);

  return (
    <div className="w-full flex flex-col gap-4 text-slate-700">
      <div className="p-4 bg-white border border-slate-200/80 rounded-2xl flex flex-wrap gap-4 items-end justify-between shadow-xs">
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Search Merchant</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="E.g., Whole Foods"
                value={merchantSearch}
                onChange={(e) => setMerchantSearch(e.target.value)}
                className="bg-white border border-slate-200 text-slate-800 placeholder-slate-400 text-xs rounded-xl px-3 py-1.5 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all w-48"
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 text-slate-700 font-medium rounded-xl text-xs border border-slate-200 transition-all cursor-pointer"
              >
                Search
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setPage(1);
              }}
              className="bg-white border border-slate-200 text-slate-850 text-xs rounded-xl px-3 py-1.5 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
            >
              <option value="">All Categories</option>
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

          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="bg-white border border-slate-200 text-slate-800 text-xs rounded-xl px-3 py-1.5 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
            />
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="bg-white border border-slate-200 text-slate-800 text-xs rounded-xl px-3 py-1.5 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
            />
          </div>
        </form>

        <button
          onClick={() => {
            setEditingTransaction(null);
            setIsFormOpen(true);
          }}
          className="px-4 py-2 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-650 hover:opacity-95 text-white font-medium rounded-xl text-xs transition-all shadow-md shadow-indigo-600/10 flex items-center gap-1.5 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Transaction
        </button>
      </div>

      <div className="bg-white border border-slate-200/80 rounded-2xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500 text-[10px] font-semibold uppercase tracking-wider">
                <th className="px-6 py-4">Date</th>
                <th className="px-6 py-4">Merchant</th>
                <th className="px-6 py-4">Category</th>
                <th className="px-6 py-4">Source</th>
                <th className="px-6 py-4 text-right">Amount</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-slate-400 font-medium">
                    Loading transactions...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-slate-450 font-medium">
                    No transactions found.
                  </td>
                </tr>
              ) : (
                items.map((txn) => (
                  <tr key={txn.id} className="hover:bg-slate-50/40 transition-colors">
                    <td className="px-6 py-4 font-mono text-slate-500">{txn.date}</td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{txn.merchant}</div>
                      <div className="text-[10px] text-slate-400 max-w-xs truncate">{txn.raw_description}</div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-50 border border-slate-200 text-slate-700 capitalize">
                        {txn.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-[10px] uppercase text-slate-450">{txn.source}</td>
                    <td className={`px-6 py-4 text-right font-bold font-mono ${txn.amount < 0 ? "text-rose-650" : "text-emerald-600"}`}>
                      {txn.amount < 0 ? "-" : "+"}{formatMoney(txn.amount, txn.currency)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => {
                            setEditingTransaction(txn);
                            setIsFormOpen(true);
                          }}
                          className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-slate-50 border border-transparent hover:border-slate-200 rounded-lg transition-all cursor-pointer"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDelete(txn.id)}
                          className="p-1 text-slate-400 hover:text-rose-650 hover:bg-slate-50 border border-transparent hover:border-slate-200 rounded-lg transition-all cursor-pointer"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="px-6 py-4 bg-slate-50/30 border-t border-slate-100 flex items-center justify-between">
            <span className="text-[11px] text-slate-500 font-medium">
              Showing page {page} of {totalPages} ({total} items total)
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 disabled:opacity-50 hover:bg-slate-50 rounded-xl text-xs font-semibold transition-all cursor-pointer"
              >
                Previous
              </button>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 disabled:opacity-50 hover:bg-slate-50 rounded-xl text-xs font-semibold transition-all cursor-pointer"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 relative">
            <TransactionForm
              transaction={editingTransaction}
              onSuccess={() => {
                setIsFormOpen(false);
                setEditingTransaction(null);
                onRefresh();
              }}
              onCancel={() => {
                setIsFormOpen(false);
                setEditingTransaction(null);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
