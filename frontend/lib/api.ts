/**
 * IncidentHub API Client Utility
 *
 * Base URL resolution, health checks, and domain foundation API client functions.
 */

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export interface BackendHealthResponse {
  status: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DomainFoundationStatusData {
  connected: boolean;
  organizationCount: number;
  userCount: number;
  error?: string;
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

export async function fetchOrganizations(): Promise<Organization[]> {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/organizations`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch organizations: ${res.statusText}`);
  }
  return (await res.json()) as Organization[];
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch(`${getApiBaseUrl()}/api/v1/users`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch users: ${res.statusText}`);
  }
  return (await res.json()) as User[];
}

export async function fetchDomainFoundationStatus(): Promise<DomainFoundationStatusData> {
  try {
    const [orgs, users] = await Promise.all([fetchOrganizations(), fetchUsers()]);
    return {
      connected: true,
      organizationCount: orgs.length,
      userCount: users.length,
    };
  } catch (err: unknown) {
    return {
      connected: false,
      organizationCount: 0,
      userCount: 0,
      error: err instanceof Error ? err.message : "Unable to reach domain API",
    };
  }
}
