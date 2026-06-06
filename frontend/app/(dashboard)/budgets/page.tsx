"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchWithAuth } from "../../../lib/api";
import BudgetCard, { BudgetStatus } from "../../../components/budget/BudgetCard";

export default function BudgetsPage() {
  const { getToken } = useAuth();
  const [statuses, setStatuses] = useState<BudgetStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterPeriod, setFilterPeriod] = useState<"all" | "monthly" | "yearly">("all");
  
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState<BudgetStatus | null>(null);
  
  const [category, setCategory] = useState("groceries");
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");
  const [limitAmount, setLimitAmount] = useState("");
  
  const [formLoading, setFormLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadBudgets = async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const data = await fetchWithAuth("/api/v1/budgets/status", { token });
      setStatuses(data);
    } catch (err) {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBudgets();
  }, []);

  const openCreateForm = () => {
    setEditingBudget(null);
    setCategory("groceries");
    setPeriod("monthly");
    setLimitAmount("");
    setFormError(null);
    setIsFormOpen(true);
  };

  const openEditForm = (budget: BudgetStatus) => {
    setEditingBudget(budget);
    setCategory(budget.category);
    setPeriod(budget.period);
    setLimitAmount(String(budget.limit));
    setFormError(null);
    setIsFormOpen(true);
  };

  const handleDelete = async (category: string, period: string) => {
    const budgetToDelete = statuses.find(s => s.category === category && s.period === period);
    if (!budgetToDelete || !budgetToDelete.id) return;

    if (!confirm(`Are you sure you want to delete the ${period} budget for ${category}?`)) {
      return;
    }

    try {
      const token = await getToken();
      await fetchWithAuth(`/api/v1/budgets/${budgetToDelete.id}`, {
        method: "DELETE",
        token
      });
      loadBudgets();
    } catch (err) {
    }
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormLoading(true);
    setFormError(null);
    
    try {
      const token = await getToken();
      const payload = {
        category,
        period,
        limit_amount: parseFloat(limitAmount)
      };

      await fetchWithAuth("/api/v1/budgets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        token
      });

      setIsFormOpen(false);
      loadBudgets();
    } catch (err: any) {
      setFormError(err.message || "Failed to save budget");
    } finally {
      setFormLoading(false);
    }
  };

  const filteredStatuses = statuses.filter(s => {
    if (filterPeriod === "all") return true;
    return s.period === filterPeriod;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight">Budget Planner</h1>
          <p className="text-xs text-zinc-400 mt-1">Set spending limits per category and track your progress.</p>
        </div>

        <button
          onClick={openCreateForm}
          className="px-4 py-2 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 hover:opacity-95 text-white font-medium rounded-xl text-xs transition-all shadow-lg shadow-indigo-500/10 flex items-center gap-1.5"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Configure Budget
        </button>
      </div>

      <div className="flex border-b border-zinc-900 gap-6">
        <button
          onClick={() => setFilterPeriod("all")}
          className={`pb-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 ${
            filterPeriod === "all"
              ? "border-indigo-500 text-white"
              : "border-transparent text-zinc-500 hover:text-zinc-350"
          }`}
        >
          All Budgets
        </button>
        <button
          onClick={() => setFilterPeriod("monthly")}
          className={`pb-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 ${
            filterPeriod === "monthly"
              ? "border-indigo-500 text-white"
              : "border-transparent text-zinc-500 hover:text-zinc-350"
          }`}
        >
          Monthly
        </button>
        <button
          onClick={() => setFilterPeriod("yearly")}
          className={`pb-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 ${
            filterPeriod === "yearly"
              ? "border-indigo-500 text-white"
              : "border-transparent text-zinc-500 hover:text-zinc-350"
          }`}
        >
          Yearly
        </button>
      </div>

      {loading ? (
        <div className="py-20 text-center text-zinc-500 font-medium text-sm">
          Loading budget configurations...
        </div>
      ) : filteredStatuses.length === 0 ? (
        <div className="py-20 bg-zinc-900/10 border border-dashed border-zinc-800 rounded-2xl text-center text-zinc-500 max-w-xl mx-auto flex flex-col items-center gap-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <div>
            <p className="font-semibold text-white text-sm">No Budgets Configured</p>
            <p className="text-xs text-zinc-600 mt-1">Start tracking your spending by configuring a monthly or yearly budget limit.</p>
          </div>
          <button
            onClick={openCreateForm}
            className="px-3.5 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold rounded-xl border border-zinc-800 transition-all"
          >
            Configure First Budget
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredStatuses.map((budget, idx) => (
            <BudgetCard
              key={`${budget.category}-${budget.period}-${idx}`}
              status={budget}
              onEdit={openEditForm}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {isFormOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-zinc-905 border border-zinc-800 rounded-2xl shadow-2xl p-6 relative text-zinc-300">
            <h3 className="text-lg font-bold text-white mb-4">
              {editingBudget ? "Edit Budget Limit" : "Configure Budget Limit"}
            </h3>

            {formError && (
              <div className="p-3 bg-red-955/30 border border-red-800 text-red-400 rounded-xl text-xs mb-4">
                {formError}
              </div>
            )}

            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Category</label>
                <select
                  disabled={!!editingBudget}
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full bg-zinc-955 border border-zinc-800 text-white rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
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

              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Period</label>
                <select
                  disabled={!!editingBudget}
                  value={period}
                  onChange={(e) => setPeriod(e.target.value as any)}
                  className="w-full bg-zinc-955 border border-zinc-800 text-white rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50"
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Limit Amount ($)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  placeholder="0.00"
                  value={limitAmount}
                  onChange={(e) => setLimitAmount(e.target.value)}
                  className="w-full bg-zinc-955 border border-zinc-800 text-white rounded-xl px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsFormOpen(false)}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium rounded-xl border border-zinc-800 transition-all text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formLoading}
                  className="px-4 py-2 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 hover:opacity-95 text-white font-medium rounded-xl transition-all shadow-lg shadow-indigo-500/10 text-xs disabled:opacity-50"
                >
                  {formLoading ? "Saving..." : "Save Budget"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
