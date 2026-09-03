"use client";

import { useEffect } from "react";
import { captureFrontendError } from "@/lib/telemetry";

/**
 * Last-resort boundary: catches errors thrown by the root layout itself,
 * which `app/error.tsx` sits inside and therefore cannot catch.
 *
 * It replaces the whole document, so it must render its own <html> and
 * <body> — and it cannot rely on the app's layout, fonts, or providers,
 * since the failure may be in one of those. The styles are inline for
 * the same reason.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
    void captureFrontendError(error, "app/global-error", true);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#f8fafc",
          fontFamily:
            "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
          color: "#7f1d1d",
        }}
      >
        <div
          role="alert"
          style={{
            maxWidth: "28rem",
            padding: "1.5rem",
            border: "1px solid #fca5a5",
            background: "#fef2f2",
            borderRadius: "0.5rem",
          }}
        >
          <h1 style={{ fontSize: "1rem", margin: 0, fontWeight: 600 }}>
            TrackFlow couldn&apos;t start
          </h1>
          <p style={{ fontSize: "0.875rem", marginTop: "0.5rem" }}>
            Something went wrong before the page could be displayed. Reloading
            usually fixes it.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "1rem",
              padding: "0.375rem 0.75rem",
              fontSize: "0.875rem",
              fontWeight: 500,
              color: "#7f1d1d",
              background: "#fff",
              border: "1px solid #f87171",
              borderRadius: "0.375rem",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
          <p style={{ fontSize: "0.75rem", marginTop: "1rem" }}>
            If it keeps happening, contact the platform team
            {error.digest ? ` and quote reference ${error.digest}` : ""}.
          </p>
        </div>
      </body>
    </html>
  );
}
