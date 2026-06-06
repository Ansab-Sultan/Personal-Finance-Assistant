/**
 * Format an absolute money amount in the given currency, using the proper symbol and
 * placement for the locale. Falls back to "CODE 12.34" if the currency code is invalid.
 */
export function formatMoney(amount: number, currency?: string): string {
  const code = (currency || "USD").toUpperCase();
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: code }).format(Math.abs(amount));
  } catch {
    return `${code} ${Math.abs(amount).toFixed(2)}`;
  }
}
