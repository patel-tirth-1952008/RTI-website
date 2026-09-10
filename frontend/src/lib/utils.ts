import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return "N/A";
  try {
    // Append 'Z' if missing so JavaScript correctly parses UTC strings
    // and converts them to the user's local timezone (IST for India)
    const str =
      dateString.endsWith("Z") || dateString.includes("+")
        ? dateString
        : dateString.replace(" ", "T") + "Z";

    const date = new Date(str);

    // Guard against invalid dates
    if (isNaN(date.getTime())) return dateString;

    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
  } catch {
    return dateString;
  }
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    draft: "bg-gray-500",
    generated: "bg-blue-500",
    review_pending: "bg-yellow-500",
    filing_in_progress: "bg-purple-500",
    filed_successfully: "bg-green-500",
    filing_failed: "bg-red-500",
    response_received: "bg-emerald-500",
    first_appeal: "bg-orange-500",
    second_appeal: "bg-red-600",
    closed: "bg-gray-600",
  };
  return colors[status] || "bg-gray-500";
}

export function getStatusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export function getCategoryIcon(category: string): string {
  const icons: Record<string, string> = {
    road_repair: "🛣️",
    water_supply: "💧",
    electricity: "⚡",
    sanitation: "🧹",
    education: "📚",
    healthcare: "🏥",
    corruption: "⚖️",
    government_scheme: "📋",
    land_records: "🗺️",
    police: "🚔",
    environment: "🌿",
    public_transport: "🚌",
    general: "📝",
  };
  return icons[category] || "📝";
}