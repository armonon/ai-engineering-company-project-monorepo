"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { useAuth } from "@/components/AuthProvider";
import {
  captureFrontendError,
  endpointTemplate,
  track,
  viewportClass,
} from "@/lib/telemetry";

type Section =
  | "freight_quote"
  | "incidents"
  | "inventory"
  | "suppliers"
  | "account"
  | "authentication";

function sectionForPath(pathname: string): Section {
  if (pathname.startsWith("/backoffice/inventory") || pathname.startsWith("/inventory")) {
    return "inventory";
  }
  if (pathname.startsWith("/incident")) return "incidents";
  if (pathname.startsWith("/suppliers")) return "suppliers";
  if (pathname.startsWith("/account")) return "account";
  if (["/login", "/register", "/forgot-password", "/reset-password"].some(
    (route) => pathname.startsWith(route),
  )) {
    return "authentication";
  }
  return "freight_quote";
}

function currentNavigationType(): "initial" | "spa" | "reload" {
  if (typeof performance === "undefined") return "initial";
  const navigation = performance.getEntriesByType("navigation")[0] as
    | PerformanceNavigationTiming
    | undefined;
  if (navigation?.type === "reload") return "reload";
  return "initial";
}

/** Cross-cutting capture for navigation, Web Vitals, and uncaught errors. */
export function TelemetryRuntime() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const previousSection = useRef<Section | "direct">("direct");
  const lastTrackedPath = useRef<string | null>(null);
  const pageViewCount = useRef(0);
  const reportedLcp = useRef(false);

  useEffect(() => {
    if (loading && !pathname.startsWith("/login") && !pathname.startsWith("/register")) {
      return;
    }
    // Auth restoration and React Strict Mode can both re-run this effect
    // without a navigation. One URL transition is one page-view event.
    if (lastTrackedPath.current === pathname) return;
    const section = sectionForPath(pathname);
    track("page_viewed", {
      route_template: endpointTemplate(pathname),
      section,
      previous_section: previousSection.current,
      viewport_class: viewportClass(),
    });
    previousSection.current = section;
    lastTrackedPath.current = pathname;
    pageViewCount.current += 1;
  }, [loading, pathname, user]);

  useEffect(() => {
    const onWindowError = (event: ErrorEvent) => {
      void captureFrontendError(event.error ?? new Error(event.message), "window.onerror", false);
    };
    const onUnhandledRejection = (event: PromiseRejectionEvent) => {
      void captureFrontendError(event.reason, "unhandledrejection", false);
    };
    window.addEventListener("error", onWindowError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onWindowError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);

  useReportWebVitals((metric) => {
    if (metric.name !== "LCP" || reportedLcp.current) return;
    reportedLcp.current = true;
    const duration = Math.max(0, Math.round(metric.value));
    track("page_load_recorded", {
      route_template: endpointTemplate(window.location.pathname),
      duration_ms: duration,
      navigation_type: pageViewCount.current > 1 ? "spa" : currentNavigationType(),
      viewport_class: viewportClass(),
      threshold_exceeded: duration > 2_500,
    });
  });

  return null;
}
