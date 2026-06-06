import { SignIn } from "@clerk/nextjs";

/**
 * Styled Clerk SignIn page component with premium gradient background.
 */
export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-4 relative">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/30 via-zinc-950 to-zinc-950 pointer-events-none" />
      <div className="relative w-full max-w-md flex flex-col items-center gap-6 z-10">
        <div className="flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <span className="text-xl font-bold text-white">R</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white mt-2">Revonix</h1>
          <p className="text-sm text-zinc-400">Unlock your financial intelligence</p>
        </div>
        <SignIn
          appearance={{
            elements: {
              card: "bg-zinc-950/60 backdrop-blur-xl border border-zinc-800 shadow-2xl rounded-2xl text-white",
              headerTitle: "text-white text-xl font-bold",
              headerSubtitle: "text-zinc-400 text-sm",
              socialButtonsBlockButton: "bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-white rounded-xl transition-all duration-200",
              formButtonPrimary: "bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 hover:opacity-95 text-white font-medium rounded-xl transition-all duration-200 shadow-lg shadow-indigo-500/10",
              formFieldLabel: "text-zinc-300 font-medium",
              formFieldInput: "bg-zinc-900 border border-zinc-800 text-white rounded-xl focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all",
              footerActionLink: "text-indigo-400 hover:text-indigo-300 font-medium transition-all"
            }
          }}
        />
      </div>
    </div>
  );
}
