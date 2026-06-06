import { redirect } from "next/navigation";

/**
 * Root page component that redirects logged-in or authenticated users to the dashboard.
 */
export default function HomePage() {
  redirect("/transactions");
}
