import { authJson } from "@/lib/auth";
import { askTrackFlow } from "@/lib/knowledge";

jest.mock("@/lib/auth", () => ({ authJson: jest.fn() }));

const mockedAuthJson = jest.mocked(authJson);

describe("TrackFlow knowledge integration", () => {
  beforeEach(() => mockedAuthJson.mockReset());

  it("posts the question through the central authenticated API layer", async () => {
    mockedAuthJson.mockResolvedValue({ answer: "Verified policy answer" });

    await expect(askTrackFlow("Can we discount storage?")).resolves.toEqual({
      answer: "Verified policy answer",
    });
    expect(mockedAuthJson).toHaveBeenCalledWith("/knowledge/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: "Can we discount storage?" }),
    });
  });

  it("does not swallow readable service failures", async () => {
    mockedAuthJson.mockRejectedValue(new Error("Knowledge service is warming up."));
    await expect(askTrackFlow("What is our SLA?")).rejects.toThrow(
      "Knowledge service is warming up.",
    );
  });
});
