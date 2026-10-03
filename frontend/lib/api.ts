/**
 * IncidentHub API Client Utility
 *
 * Base URL resolution and foundation health checks for the frontend.
 */

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export interface BackendHealthResponse {
  status: string;
}

export async function checkBackendHealth(): Promise<BackendHealthResponse | null> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/health`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    });
    if (!res.ok) {
      return null;
    }
    return (await res.json()) as BackendHealthResponse;
  } catch {
    return null;
  }
}
