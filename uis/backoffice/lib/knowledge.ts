import { authJson } from "@/lib/auth";

export interface KnowledgeAnswer {
  answer: string;
}
export function askTrackFlow(question: string): Promise<KnowledgeAnswer> {
  return authJson<KnowledgeAnswer>("/knowledge/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
