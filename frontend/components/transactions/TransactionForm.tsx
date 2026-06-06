"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../lib/api";

interface TransactionFormProps {
  transaction?: any;
  onSuccess: () => void;
  onCancel: () => void;
}

/**
 * TransactionForm component for creating or editing individual transactions.
 * Handles duplicate checking with conflict confirmation (HTTP 409).
 */
export default function TransactionForm({ transaction, onSuccess, onCancel }: TransactionFormProps) {
  const { getToken } = useAuth();
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [merchant, setMerchant] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("uncategorized");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<any | null>(null);

  useEffect(() => {
    if (transaction) {
      setDate(transaction.date || "");
      setAmount(String(Math.abs(transaction.amount)) || "");
      setCurrency(transaction.currency || "USD");
      setMerchant(transaction.merchant || "");
      setDescription(transaction.raw_description || "");
      setCategory(transaction.category || "uncategorized");
    }
  }, [transaction]);

  const handleSubmit = async (e: React.FormEvent, force: boolean = false) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    if (!force) {
      setConflict(null);
    }
    
    try {
      const token = await getToken();
      const parsedAmount = Math.abs(parseFloat(amount));
      const isCredit = category === "income" || category === "transfer";
      const payload = {
        date,
        amount: isCredit ? parsedAmount : -parsedAmount,
        currency,
        merchant,
        raw_description: description || merchant,
        category,
        source: transaction ? transaction.source : "manual",
      };
      
      const url = transaction 
        ? `/api/v1/transactions/${transaction.id}`
        : `/api/v1/transactions?force=${force}`;
        
      await fetchWithAuth(url, {
        method: transaction ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        token
      });
      
      onSuccess();
    } catch (err: any) {
      if (err.status === 409) {
        setConflict(err.message.existing_transaction || err.message);
      } else {
        setError(err.message || "Something went wrong");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={(e) => handleSubmit(e, false)} className="space-y-4 text-slate-700">
      <h3 className="text-lg font-bold text-slate-900 mb-2">
        {transaction ? "Edit Transaction" : "Add Manual Transaction"}
      </h3>
      
      {error && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-605 rounded-xl text-xs">
          {error}
        </div>
      )}

      {conflict && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs space-y-3 shadow-2xs">
          <p className="text-amber-700 font-semibold">Potential duplicate transaction found:</p>
          <div className="bg-white p-2.5 rounded-lg border border-slate-200 text-slate-600 space-y-1 shadow-3xs">
            <p>Merchant: <span className="text-slate-900 font-medium">{conflict.merchant}</span></p>
            <p>Date: <span className="text-slate-900 font-medium">{conflict.date}</span></p>
            <p>Amount: <span className="text-slate-900 font-semibold">${conflict.amount}</span></p>
          </div>
          <p className="text-slate-600">Are you sure you want to add this transaction anyway?</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={(e) => handleSubmit(e, true)}
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-lg transition-all cursor-pointer shadow-sm"
            >
              Yes, Add it
            </button>
            <button
              type="button"
              onClick={() => setConflict(null)}
              className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 rounded-lg transition-all border border-slate-205 cursor-pointer shadow-2xs"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-505 uppercase tracking-wider mb-1">Date</label>
          <input
            type="date"
            required
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-505 uppercase tracking-wider mb-1">Amount ($)</label>
          <input
            type="number"
            step="0.01"
            required
            placeholder="0.00"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-slate-505 uppercase tracking-wider mb-1">Merchant</label>
          <input
            type="text"
            required
            placeholder="E.g., Starbucks"
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-505 uppercase tracking-wider mb-1">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full bg-white border border-slate-200 text-slate-850 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all cursor-pointer"
          >
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

      <div>
        <label className="block text-xs font-semibold text-slate-505 uppercase tracking-wider mb-1">Description / Memo</label>
        <input
          type="text"
          placeholder="E.g., Dinner with team"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full bg-white border border-slate-200 text-slate-900 rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
        />
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 bg-slate-50 hover:bg-slate-100 text-slate-650 font-medium rounded-xl border border-slate-200 transition-all text-sm cursor-pointer"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading || !!conflict}
          className="px-4 py-2 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-650 hover:opacity-95 text-white font-medium rounded-xl transition-all shadow-md shadow-indigo-600/10 text-sm disabled:opacity-50 cursor-pointer"
        >
          {loading ? "Saving..." : "Save"}
        </button>
      </div>
    </form>
  );
}
