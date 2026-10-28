import { authJson } from "@/lib/auth";
import {
  fetchAgentDetail,
  fetchExecutionLog,
  fetchObservedAgents,
  fetchObservedFlows,
} from "@/lib/observability";

jest.mock("@/lib/auth", () => ({
  authFetch: jest.fn(),
  authJson: jest.fn(),
  readApiError: jest.fn(),
}));

const mockedJson = jest.mocked(authJson);

describe("agent observability integration", () => {
  beforeEach(() => mockedJson.mockReset());

  it("loads agent, flow, detail, and paginated history through authenticated APIs", async () => {
    mockedJson.mockResolvedValue({});
    await fetchObservedAgents();
    await fetchAgentDetail("rfp_pipeline");
    await fetchObservedFlows();
    await fetchExecutionLog(2, { agentId: "rfp_pipeline", flowId: "rfp-1" });

    expect(mockedJson).toHaveBeenNthCalledWith(1, "/observability/agents");
    expect(mockedJson).toHaveBeenNthCalledWith(2, "/observability/agents/rfp_pipeline");
    expect(mockedJson).toHaveBeenNthCalledWith(3, "/observability/flows");
    expect(mockedJson).toHaveBeenNthCalledWith(
      4,
      "/observability/executions?page=2&page_size=20&agent_id=rfp_pipeline&flow_id=rfp-1",
    );
  });
});
