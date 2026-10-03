"use client";

import { useEffect, useState } from "react";
import { checkBackendHealth } from "@/lib/api";

export function BackendStatus() {
  const [status, setStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [details, setDetails] = useState<string>("Checking backend connection...");

  useEffect(() => {
    let mounted = true;

    async function verify() {
      const result = await checkBackendHealth();
      if (!mounted) return;

      if (result && result.status === "ok") {
        setStatus("connected");
        setDetails("FastAPI service reachable (GET /health -> 200 OK)");
      } else {
        setStatus("disconnected");
        setDetails("Backend service currently unreachable or not running on port 8000");
      }
    }

    verify();
    const interval = setInterval(verify, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300 backdrop-blur-sm">
      <div className="relative flex h-3 w-3 items-center justify-center">
        {status === "connected" && (
          <>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </>
        )}
        {status === "checking" && (
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-400 animate-pulse" />
        )}
        {status === "disconnected" && (
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-500" />
        )}
      </div>

      <div className="flex-1">
        <div className="font-medium text-slate-200">
          Backend Service Status:{" "}
          <span
            className={
              status === "connected"
                ? "text-emerald-400"
                : status === "checking"
                  ? "text-amber-400"
                  : "text-rose-400"
            }
          >
            {status.toUpperCase()}
          </span>
        </div>
        <div className="text-xs text-slate-400 mt-0.5">{details}</div>
      </div>
    </div>
  );
}
