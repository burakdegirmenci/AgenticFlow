import axios, { AxiosError } from "axios";

export const apiClient = axios.create({
  baseURL: "/api",
  timeout: 60_000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    // Rewrite axios errors so callers see the FastAPI `detail` string as the
    // thrown Error's message. Anything else (network errors, etc.) is
    // re-thrown unchanged.
    if (error instanceof AxiosError && error.response) {
      const data = error.response.data as { detail?: unknown } | null | undefined;
      const detail =
        (typeof data?.detail === "string" && data.detail) ||
        error.response.statusText ||
        "Request failed";
      error.message = detail;
    }
    return Promise.reject(error instanceof Error ? error : new Error(String(error)));
  },
);
