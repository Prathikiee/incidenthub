import { BackendStatus } from "@/components/BackendStatus";
import { DomainFoundationStatus } from "@/components/DomainFoundationStatus";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-950 font-sans text-slate-100">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white font-bold shadow-md shadow-indigo-600/30">
              IH
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white">IncidentHub</span>
              <span className="ml-2.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[11px] font-medium text-indigo-400">
                Milestone 2 • Core Domain Foundation
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span className="hidden sm:inline">Modular Monolith Architecture</span>
            <div className="h-4 w-px bg-slate-800" />
            <a
              href="https://github.com/Prathikiee/incidenthub"
              target="_blank"
              rel="noreferrer"
              className="text-slate-300 hover:text-white transition-colors"
            >
              GitHub Repository
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-12">
        {/* Hero Section */}
        <section className="mb-12 max-w-3xl">
          <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
            Incident Intelligence & <br />
            <span className="bg-gradient-to-r from-indigo-400 via-sky-400 to-teal-400 bg-clip-text text-transparent">
              Temporal Response Workspace
            </span>
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-slate-300">
            IncidentHub is designed to reconstruct operational incidents as{" "}
            <span className="font-semibold text-white">temporal evidence stories</span>, moving
            beyond static ticket and incident CRUD workflows into causal understanding and
            deterministic replay.
          </p>
        </section>

        {/* Live Service Status */}
        <section className="mb-12">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Live Development Connectivity
          </div>
          <div className="flex flex-col gap-3">
            <BackendStatus />
            <DomainFoundationStatus />
          </div>
        </section>

        {/* Architecture Foundation Grid */}
        <section className="mb-14">
          <div className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Milestone 2 Domain Foundation
          </div>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {/* Frontend Card */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
              <div className="text-xs font-mono uppercase tracking-wider text-indigo-400 mb-2">
                Frontend
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Next.js + TypeScript</h3>
              <p className="text-xs leading-relaxed text-slate-400 mb-3">
                Next.js App Router, React 19, TypeScript, and Tailwind CSS configured for
                independent operation.
              </p>
              <div className="text-[11px] font-mono text-slate-500">
                Port: 3000 • Standalone or Docker
              </div>
            </div>

            {/* Backend Card */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
              <div className="text-xs font-mono uppercase tracking-wider text-sky-400 mb-2">
                Backend
              </div>
              <h3 className="text-base font-semibold text-white mb-2">FastAPI + Pydantic v2</h3>
              <p className="text-xs leading-relaxed text-slate-400 mb-3">
                Async web service with operational health probe (
                <code className="text-slate-300">/health</code>) and versioned routing (
                <code className="text-slate-300">/api/v1</code>).
              </p>
              <div className="text-[11px] font-mono text-slate-500">
                Port: 8000 • Pytest + Ruff + MyPy
              </div>
            </div>

            {/* Database Card */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
              <div className="text-xs font-mono uppercase tracking-wider text-teal-400 mb-2">
                Persistence
              </div>
              <h3 className="text-base font-semibold text-white mb-2">PostgreSQL + SQLAlchemy</h3>
              <p className="text-xs leading-relaxed text-slate-400 mb-3">
                SQLAlchemy 2.x asyncpg and Alembic migrations for Organizations, Users, Teams,
                Services, and Service Dependencies.
              </p>
              <div className="text-[11px] font-mono text-slate-500">
                Port: 5432 • Environment-configured
              </div>
            </div>

            {/* Infrastructure Card */}
            <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
              <div className="text-xs font-mono uppercase tracking-wider text-violet-400 mb-2">
                Orchestration
              </div>
              <h3 className="text-base font-semibold text-white mb-2">Docker Compose</h3>
              <p className="text-xs leading-relaxed text-slate-400 mb-3">
                Unified multi-container environment uniting frontend, backend, and postgres on an
                isolated bridge network.
              </p>
              <div className="text-[11px] font-mono text-slate-500">docker compose up --build</div>
            </div>
          </div>
        </section>

        {/* Product Vision & Story Concept */}
        <section className="rounded-2xl border border-slate-800 bg-slate-900/30 p-8 backdrop-blur-sm">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            Core Product Philosophy
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white mb-4">
            The Incident Story Concept
          </h2>
          <p className="text-sm leading-relaxed text-slate-300 mb-6 max-w-3xl">
            Conventional tools treat incidents as tickets with status fields. IncidentHub treats an
            incident as an evolving temporal story comprising state, evidence, human hypotheses, and
            action consequences:
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 text-xs text-slate-300">
            <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-4">
              <div className="font-semibold text-white mb-1">1. Temporal Sequence</div>
              <p className="text-slate-400">
                Chronological reconstruction of what happened and when.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-4">
              <div className="font-semibold text-white mb-1">2. System State & Changes</div>
              <p className="text-slate-400">
                Deployments, config changes, and infrastructure mutations.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-4">
              <div className="font-semibold text-white mb-1">3. Evidence Observation</div>
              <p className="text-slate-400">Telemetry, logs, traces, alerts, and user reports.</p>
            </div>
            <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-4">
              <div className="font-semibold text-white mb-1">4. Responder Hypotheses</div>
              <p className="text-slate-400">
                Active theories formed, validated, or rejected by responders.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-4">
              <div className="font-semibold text-white mb-1">5. Actions & Consequences</div>
              <p className="text-slate-400">
                Interventions made and observed post-action system effects.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800/80 bg-slate-950/60 p-4">
              <div className="font-semibold text-white mb-1">6. Incident Replay</div>
              <p className="text-slate-400">
                Deterministic time-scrubbing and post-incident learning.
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-6xl px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>IncidentHub • Milestone 2 Core Domain Foundation</div>
          <div>MIT License • Production-Grade Modular Monolith</div>
        </div>
      </footer>
    </div>
  );
}
