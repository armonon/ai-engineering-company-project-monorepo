export function resolveApiBaseUrl(
  inventoryValue?: string,
  generalValue?: string,
): string {
  const configured = inventoryValue?.trim() || generalValue?.trim();
  return (configured || "/trackflow-api").replace(/\/+$/, "");
}

export const API_BASE_URL = resolveApiBaseUrl(
  process.env.NEXT_PUBLIC_INVENTORY_API_URL,
  process.env.NEXT_PUBLIC_API_BASE_URL,
);

export interface AnalysisResponse {
  totals: {
    total_rows: number;
    valid_records: number;
    invalid_records: number;
  };
  invalid_breakdown: {
    rule: string;
    label: string;
    count: number;
  }[];
  category_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  country_breakdown: Record<string, number>;
  satisfaction: {
    scored_incidents: number;
    closed_incidents: number;
    average_score: number;
    per_score: Record<string, number>;
  };
}
