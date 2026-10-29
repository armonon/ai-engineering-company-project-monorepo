import { API_BASE_URL } from "@/lib/api";

export function websocketUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  if (/^https?:\/\//.test(API_BASE_URL)) {
    return `${API_BASE_URL.replace(/^http/, "ws")}${suffix}`;
  }
  if (typeof window === "undefined") return `${API_BASE_URL}${suffix}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${API_BASE_URL}${suffix}`;
}
