import { SignIn } from "@clerk/nextjs";

/**
 * Styled Clerk SignIn page component with premium gradient background.
 */
export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4 relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-500/5 via-slate-50 to-slate-50 pointer-events-none" />
      <div className="relative w-full max-w-md flex flex-col items-center gap-6 z-10">
        <div className="flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-650 flex items-center justify-center shadow-md shadow-indigo-500/10">
            <span className="text-xl font-bold text-white">P</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 mt-2">Personal Finance Assistant</h1>
          <p className="text-sm text-slate-500">Unlock your financial intelligence</p>
        </div>
        <SignIn
          appearance={{
            elements: {
              card: "bg-white border border-slate-205 shadow-xl rounded-2xl text-slate-800",
              headerTitle: "text-slate-900 text-xl font-bold",
              headerSubtitle: "text-slate-500 text-sm",
              socialButtonsBlockButton: "bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 rounded-xl transition-all duration-200 cursor-pointer",
              formButtonPrimary: "bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-650 hover:opacity-95 text-white font-medium rounded-xl transition-all duration-200 shadow-md shadow-indigo-600/10 cursor-pointer",
              formFieldLabel: "text-slate-700 font-medium",
              formFieldInput: "bg-white border border-slate-200 text-slate-900 rounded-xl focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all",
              footerActionLink: "text-indigo-650 hover:text-indigo-700 font-medium transition-all"
            }
          }}
        />
      </div>
    </div>
  );
}
