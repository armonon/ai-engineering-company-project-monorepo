"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CandidateForm } from "@/components/talent/CandidateForm";
import {
  TalentToast,
  type ToastMessage,
} from "@/components/talent/TalentToast";
import { toUserMessage } from "@/lib/errors";
import { candidatesService } from "@/lib/talent-api";

export default function NewCandidatePage() {
  const router = useRouter();
  const [toast, setToast] = useState<ToastMessage | null>(null);

  return (
    <div className="space-y-6">
      <Link
        href="/talent"
        className="text-sm text-slate-600 hover:underline"
      >
        ← Back to candidates
      </Link>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          People &amp; Talent
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-slate-900">
          Register a new candidate
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Add an applicant whose information arrived outside the standard
          application channel.
        </p>
      </div>

      <div className="rounded-md border border-slate-200 bg-white p-6 shadow-sm">
        <CandidateForm
          submitLabel="Register candidate"
          onCancel={() => router.push("/talent")}
          onSubmit={async (data) => {
            try {
              const created = await candidatesService.create(data);
              setToast({
                kind: "success",
                text: `Registered ${created.full_name}`,
              });
              router.push(`/talent/${created.id}`);
            } catch (error) {
              setToast({
                kind: "error",
                text: toUserMessage(error, "Failed to register candidate"),
              });
            }
          }}
        />
      </div>

      <TalentToast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
