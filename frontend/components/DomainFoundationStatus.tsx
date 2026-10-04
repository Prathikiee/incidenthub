"use client";

import { useEffect, useState } from "react";
import { DomainFoundationStatusData, fetchDomainFoundationStatus } from "@/lib/api";

export function DomainFoundationStatus() {
  const [data, setData] = useState<DomainFoundationStatusData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadStatus() {
      const result = await fetchDomainFoundationStatus();
      if (!mounted) return;
      setData(result);
      setLoading(false);
    }

    loadStatus();
    const interval = setInterval(loadStatus, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300 backdrop-blur-sm">
        <span className="relative flex h-2.5 w-2.5 rounded-full bg-amber-400 animate-pulse" />
        <span className="text-slate-400 text-xs">
          Querying Core Domain API endpoints (/api/v1/organizations, /api/v1/users)...
        </span>
      </div>
    );
  }

  const isConnected = data?.connected ?? false;

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <div className="relative flex h-3 w-3 items-center justify-center">
          {isConnected ? (
            <>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
            </>
          ) : (
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-500" />
          )}
        </div>
        <div>
          <div className="font-medium text-slate-200">
            Core Domain APIs (/api/v1):{" "}
            <span className={isConnected ? "text-emerald-400" : "text-rose-400"}>
              {isConnected ? "SYNCHRONIZED" : "UNREACHABLE"}
            </span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            {isConnected
              ? "Relational models active: Organizations, Users, Teams, Services, Dependencies"
              : data?.error || "Cannot connect to backend domain services"}
          </div>
        </div>
      </div>

      {isConnected && (
        <div className="flex items-center gap-4 text-xs font-mono text-slate-300 border-t sm:border-t-0 sm:border-l border-slate-800 pt-2 sm:pt-0 sm:pl-4">
          <div>
            <span className="text-slate-500">Orgs:</span>{" "}
            <span className="text-indigo-400 font-semibold">{data?.organizationCount ?? 0}</span>
          </div>
          <div>
            <span className="text-slate-500">Users:</span>{" "}
            <span className="text-sky-400 font-semibold">{data?.userCount ?? 0}</span>
          </div>
        </div>
      )}
    </div>
  );
}
