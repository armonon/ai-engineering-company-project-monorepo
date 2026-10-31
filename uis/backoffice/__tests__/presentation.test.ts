import {
  actionLabel,
  describeTrigger,
  humanize,
  departmentName,
  initials,
  isLiveStatus,
  progressFraction,
  relativeTime,
  rfpProgress,
  RFP_STAGES,
  shortId,
  statusTone,
} from "@/lib/presentation";

describe("RFP stage progress", () => {
  it("maps every backend status onto the five visible stages", () => {
    expect(rfpProgress("analyzing")).toEqual({ current: 0, working: true, discarded: false });
    expect(rfpProgress("intake_complete").current).toBe(1);
    expect(rfpProgress("drafting")).toEqual({ current: 1, working: true, discarded: false });
    expect(rfpProgress("under_evaluation").current).toBe(2);
    expect(rfpProgress("needs_human_review").current).toBe(2);
    expect(rfpProgress("waiting_for_approval").current).toBe(3);
    expect(rfpProgress("done").current).toBe(RFP_STAGES.length);
    expect(rfpProgress("discarded").discarded).toBe(true);
  });

  it("fills the track proportionally and never overflows", () => {
    expect(progressFraction(rfpProgress("analyzing"))).toBe(0);
    expect(progressFraction(rfpProgress("under_evaluation"))).toBe(0.5);
    expect(progressFraction(rfpProgress("done"))).toBe(1);
    expect(progressFraction(rfpProgress("discarded"))).toBe(0);
  });
});

describe("labels and tones", () => {
  it("uses TrackFlow department names from the briefing", () => {
    expect(departmentName("warehouse")).toBe("Warehouse Operations");
    expect(departmentName("reverse")).toBe("Reverse Logistics");
    expect(departmentName("unknown_team")).toBe("Unknown team");
  });

  it("builds avatar initials from contact names", () => {
    expect(initials("Ana Whitfield")).toBe("AW");
    expect(initials("Sofía Ramos")).toBe("SR");
    expect(initials("Valentina")).toBe("VA");
    expect(initials("  ")).toBe("?");
  });

  it("turns raw action types into readable steps", () => {
    expect(actionLabel("write")).toBe("Draft written");
    expect(actionLabel("deliver")).toBe("Delivered");
    expect(actionLabel("custom_step")).toBe("Custom step");
    expect(actionLabel("tool_call")).toBe("Company data looked up");
  });

  it("keeps acronyms and shortens trigger references", () => {
    expect(humanize("rfp_workflow")).toBe("RFP workflow");
    expect(humanize("cx_chat_session")).toBe("CX chat session");
    expect(describeTrigger("rfp_ticket:6213ee4b-dbc7-42f8-9f33-027ff93dd83")).toBe("RFP ticket #6213ee4b");
    expect(describeTrigger("schedule")).toBe("Schedule");
  });

  it("marks only in-flight states as live", () => {
    expect(isLiveStatus("analyzing")).toBe(true);
    expect(isLiveStatus("running")).toBe(true);
    expect(isLiveStatus("done")).toBe(false);
    expect(statusTone("done")).toBe("emerald");
    expect(statusTone("something_new")).toBe("slate");
  });

  it("shortens ids for display", () => {
    expect(shortId("task_368718b13e814ebd9d7465eeba3616f1")).toBe("368718b1");
    expect(shortId("rfp-023b51d1-8a4d")).toBe("023b51d1");
    expect(shortId("abc")).toBe("abc");
  });
});

describe("relativeTime", () => {
  const now = new Date("2026-10-30T12:00:00Z");

  it("formats recent and older timestamps", () => {
    expect(relativeTime("2026-10-30T11:59:40Z", now)).toBe("just now");
    expect(relativeTime("2026-10-30T11:55:00Z", now)).toBe("5 min ago");
    expect(relativeTime("2026-10-30T09:00:00Z", now)).toBe("3 h ago");
    expect(relativeTime("2026-10-28T12:00:00Z", now)).toBe("2 d ago");
    expect(relativeTime("not a date", now)).toBe("");
  });
});
