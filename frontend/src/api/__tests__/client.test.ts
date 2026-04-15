import { AxiosError, type AxiosResponse } from "axios";
import { beforeEach, describe, expect, it } from "vitest";

import { apiClient } from "../client";

/** Build a realistic AxiosError instance for interceptor testing. */
function makeAxiosError(partial: {
  message: string;
  status?: number;
  statusText?: string;
  data?: unknown;
}): AxiosError {
  const err = new AxiosError(partial.message);
  if (partial.status !== undefined) {
    err.response = {
      status: partial.status,
      statusText: partial.statusText ?? "",
      data: partial.data ?? null,
      headers: {},
      config: {} as AxiosResponse["config"],
    };
  }
  return err;
}

describe("apiClient", () => {
  it("sets /api baseURL and JSON content type", () => {
    expect(apiClient.defaults.baseURL).toBe("/api");
    expect(apiClient.defaults.headers["Content-Type"]).toBe("application/json");
  });

  it("has a generous timeout for SOAP-backed endpoints", () => {
    // SOAP calls through Ticimax can be slow; clients expect a long leash.
    expect(apiClient.defaults.timeout).toBeGreaterThanOrEqual(30_000);
  });
});

describe("apiClient response interceptor", () => {
  // Grab the first rejected handler registered by client.ts.
  // Each apiClient instance has exactly one response interceptor pair.
  const handlers = apiClient.interceptors.response as unknown as {
    handlers: ({ rejected: ((err: unknown) => Promise<unknown>) | null } | null)[];
  };

  let onRejected: (err: unknown) => Promise<unknown>;

  beforeEach(() => {
    const handler = handlers.handlers.find((h) => h?.rejected);
    if (!handler?.rejected) {
      throw new Error("No rejected interceptor registered");
    }
    onRejected = handler.rejected;
  });

  it("replaces error.message with FastAPI `detail` when present", async () => {
    const err = makeAxiosError({
      message: "Request failed with status code 400",
      status: 400,
      statusText: "Bad Request",
      data: { detail: "Workflow graph contains a cycle" },
    });

    await expect(onRejected(err)).rejects.toThrow("Workflow graph contains a cycle");
  });

  it("falls back to statusText when detail is missing", async () => {
    const err = makeAxiosError({
      message: "anything",
      status: 500,
      statusText: "Internal Server Error",
      data: {},
    });

    await expect(onRejected(err)).rejects.toThrow("Internal Server Error");
  });

  it("leaves network-error message intact when no response is attached", async () => {
    const err = makeAxiosError({ message: "Network Error" });
    await expect(onRejected(err)).rejects.toThrow("Network Error");
  });

  it("wraps non-Error rejections into an Error instance", async () => {
    await expect(onRejected("oops" as unknown)).rejects.toBeInstanceOf(Error);
  });
});
