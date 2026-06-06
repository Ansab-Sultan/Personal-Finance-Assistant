"use client";

import React from "react";
import { UserButton, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Premium dashboard layout component with a sidebar, user details, and route protection.
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user } = useUser();
  const pathname = usePathname();

  const navigation = [
    { name: "Overview", href: "/transactions", icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    )},
    { name: "Budgets", href: "/budgets", icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    )},
  ];

  return (
    <div className="flex h-screen bg-zinc-955 font-sans text-zinc-200">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/10 via-zinc-955 to-zinc-955 pointer-events-none" />
      <aside className="w-64 border-r border-zinc-900 bg-zinc-905 flex flex-col z-10">
        <div className="p-6 border-b border-zinc-900 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/10">
            <span className="text-white font-extrabold text-sm">R</span>
          </div>
          <span className="text-lg font-bold tracking-tight text-white">Revonix</span>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? "bg-zinc-900 border border-zinc-800 text-white"
                    : "text-zinc-400 hover:text-zinc-250 hover:bg-zinc-950/40"
                }`}
              >
                {item.icon}
                {item.name}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-zinc-900 flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <UserButton />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-white truncate">{user?.fullName || "User Profile"}</p>
              <p className="text-[10px] text-zinc-500 truncate">{user?.primaryEmailAddress?.emailAddress || ""}</p>
            </div>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto z-10 flex flex-col">
        <header className="h-16 border-b border-zinc-900 flex items-center justify-between px-8 bg-zinc-905/30 backdrop-blur-md">
          <h2 className="text-base font-bold text-white tracking-wide">
            {pathname === "/budgets" ? "Budget Tracker" : "Financial Ledger"}
          </h2>
          <div className="flex items-center gap-4">
            <span className="text-xs bg-zinc-900 px-3 py-1 rounded-full border border-zinc-850 text-zinc-400 font-medium">
              Mode: Development
            </span>
          </div>
        </header>
        <div className="flex-1 p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
