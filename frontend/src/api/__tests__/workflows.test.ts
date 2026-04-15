import type { AxiosAdapter, AxiosRequestConfig, AxiosResponse } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../client";
import {
  createWorkflow,
  deleteWorkflow,
  getWorkflow,
  listWorkflows,
  runWorkflow,
  updateWorkflow,
} from "../workflows";

/**
 * Install a mock adapter on the shared apiClient so real HTTP never fires,
 * but requests still flow through interceptors.
 */
function installAdapter(handler: (config: AxiosRequestConfig) => unknown): AxiosAdapter {
  const adapter: AxiosAdapter = (config) =>
    Promise.resolve({
      data: handler(config) ?? {},
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    } as AxiosResponse);
  apiClient.defaults.adapter = adapter;
  return adapter;
}

let originalAdapter: AxiosAdapter | undefined;

describe("workflows api", () => {
  beforeEach(() => {
    originalAdapter = apiClient.defaults.adapter as AxiosAdapter | undefined;
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("listWorkflows GETs /workflows", async () => {
    const handler = vi.fn().mockReturnValue([{ id: 1, name: "w1" }]);
    installAdapter((cfg) => handler(cfg));

    const result = await listWorkflows();

    expect(result).toEqual([{ id: 1, name: "w1" }]);
    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.method?.toLowerCase()).toBe("get");
    expect(call.url).toBe("/workflows");
  });

  it("getWorkflow GETs /workflows/:id", async () => {
    const handler = vi.fn().mockReturnValue({ id: 7, name: "detail" });
    installAdapter((cfg) => handler(cfg));

    await getWorkflow(7);

    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.method?.toLowerCase()).toBe("get");
    expect(call.url).toBe("/workflows/7");
  });

  it("createWorkflow POSTs the payload", async () => {
    const handler = vi.fn().mockReturnValue({ id: 3, name: "new" });
    installAdapter((cfg) => handler(cfg));

    await createWorkflow({
      name: "new",
      site_id: 1,
      graph_json: { nodes: [], edges: [] },
    });

    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.method?.toLowerCase()).toBe("post");
    expect(call.url).toBe("/workflows");
    expect(call.data).toContain('"name":"new"');
  });

  it("updateWorkflow PATCHes /workflows/:id", async () => {
    const handler = vi.fn().mockReturnValue({ id: 9 });
    installAdapter((cfg) => handler(cfg));

    await updateWorkflow(9, { name: "renamed" });

    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.method?.toLowerCase()).toBe("patch");
    expect(call.url).toBe("/workflows/9");
  });

  it("deleteWorkflow DELETEs /workflows/:id", async () => {
    const handler = vi.fn().mockReturnValue({});
    installAdapter((cfg) => handler(cfg));

    await deleteWorkflow(11);

    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.method?.toLowerCase()).toBe("delete");
    expect(call.url).toBe("/workflows/11");
  });

  it("runWorkflow POSTs {input_data} with defaults", async () => {
    const handler = vi.fn().mockReturnValue({ id: 100, status: "PENDING" });
    installAdapter((cfg) => handler(cfg));

    await runWorkflow(5);

    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.method?.toLowerCase()).toBe("post");
    expect(call.url).toBe("/workflows/5/run");
    expect(call.data).toContain('"input_data":{}');
  });

  it("runWorkflow forwards explicit input", async () => {
    const handler = vi.fn().mockReturnValue({ id: 101 });
    installAdapter((cfg) => handler(cfg));

    await runWorkflow(5, { reason: "demo" });

    const call = handler.mock.calls[0]?.[0] as AxiosRequestConfig;
    expect(call.data).toContain('"reason":"demo"');
  });
});
