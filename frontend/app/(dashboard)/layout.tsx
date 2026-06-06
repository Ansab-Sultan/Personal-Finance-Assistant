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
    { name: "Insights", href: "/insights", icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    )},
    { name: "Chat", href: "/chat", icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    )},
  ];

  return (
    <div className="flex h-screen bg-slate-50 font-sans text-slate-800 relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-500/5 via-slate-50 to-slate-50 pointer-events-none" />
      <aside className="w-64 border-r border-slate-200/80 bg-white flex flex-col z-10 relative">
        <div className="p-6 border-b border-slate-100 flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-600/10">
            <span className="text-white font-extrabold text-sm">P</span>
          </div>
          <span className="text-lg font-bold tracking-tight text-slate-900">Personal Finance Assistant</span>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-indigo-50/60 border border-indigo-100/80 text-indigo-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/50 border border-transparent"
                }`}
              >
                <span className={`transition-colors duration-200 ${isActive ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-650"}`}>
                  {item.icon}
                </span>
                {item.name}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-100 flex items-center justify-between bg-white/50">
          <div className="flex items-center gap-3 min-w-0">
            <UserButton />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-900 truncate">{user?.fullName || "User Profile"}</p>
              <p className="text-[10px] text-slate-500 truncate">{user?.primaryEmailAddress?.emailAddress || ""}</p>
            </div>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto z-10 flex flex-col">
        <header className="h-16 border-b border-slate-200/80 flex items-center justify-between px-8 bg-white/80 backdrop-blur-md sticky top-0 z-20">
          <h2 className="text-base font-bold text-slate-900 tracking-wide">
            {pathname === "/budgets" ? "Budget Tracker" : pathname === "/insights" ? "Insights" : pathname === "/chat" ? "AI Financial Assistant" : "Financial Ledger"}
          </h2>
          <div className="flex items-center gap-4">
            <span className="text-xs bg-slate-100 px-3 py-1 rounded-full border border-slate-200 text-slate-650 font-medium shadow-2xs">
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
