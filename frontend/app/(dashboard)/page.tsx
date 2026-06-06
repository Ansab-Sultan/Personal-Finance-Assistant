import { redirect } from "next/navigation";

/**
 * Overview redirect page.
 */
export default function DashboardPage() {
  redirect("/transactions");
}
