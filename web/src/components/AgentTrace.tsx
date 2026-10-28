/**
 * "How this was made" for one commentary line: the agents that produced it, in order, from
 * GET /agents/trace (specs/frontend.md, "Commentary, trace and audio"). Compact: one row per agent.
 * Fact Guard shows an amber badge and a before/after diff plus the issues when it fixed the line.
 */
import { useEffect, useState } from "react";
import { getTrace } from "../lib/commentary";
import { minuteLabel } from "../lib/format";
import type { MatchData } from "../lib/match";
import type { Trace, TraceStep } from "../types";

const BADGE: Record<string, string> = {
  pass: "bg-emerald-500/15 text-emerald-300",
  fixed: "bg-amber-500/20 text-amber-300",
  removed: "bg-red-500/20 text-red-300",
  template: "bg-zinc-700 text-zinc-300",
};

const MODE_LABEL = { casual: "Casual", analyst: "Analyst" } as const;
const REASON_LABEL = { cap: "the spend limit was reached", failure: "an AI step failed" } as const;

function Quote({ children }: { children: string }) {
  return <p className="text-zinc-300">“{children}”</p>;
}

/** The details under an agent's name; each agent shows the fields the contract gives it. */
function StepDetails({ step }: { step: TraceStep }) {
  switch (step.agent) {
    case "Interpreter":
      return (
        <>
          {step.summary && <p className="text-zinc-400">{step.summary}</p>}
          {step.fact_ids && step.fact_ids.length > 0 && <p className="text-xs text-zinc-500">Facts: {step.fact_ids.join(", ")}</p>}
        </>
      );
    case "Moments":
      return (
        <>
          {step.summary && <p className="text-zinc-400">{step.summary}</p>}
          {step.why && <p className="text-zinc-300">Why: {step.why}</p>}
        </>
      );
    case "Commentator":
      return (
        <>
          {step.summary && <p className="text-zinc-400">{step.summary}</p>}
          {step.text && <Quote>{step.text}</Quote>}
        </>
      );
    case "Fact Guard":
      return (
        <>
          {step.summary && <p className="text-zinc-400">{step.summary}</p>}
          {step.fact_check === "fixed" && step.before && step.after && (
            <div className="mt-1 space-y-1">
              <p className="rounded bg-red-500/10 px-2 py-1 text-red-200">
                <span className="mr-1 text-xs uppercase tracking-wide text-red-300/80">Before</span>
                <del>{step.before}</del>
              </p>
              <p className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-200">
                <span className="mr-1 text-xs uppercase tracking-wide text-emerald-300/80">After</span>
                <ins className="no-underline">{step.after}</ins>
              </p>
            </div>
          )}
          {step.fact_check === "removed" && step.before && (
            <p className="rounded bg-red-500/10 px-2 py-1 text-red-200">
              <span className="mr-1 text-xs uppercase tracking-wide text-red-300/80">Removed</span>
              <del>{step.before}</del>
            </p>
          )}
          {step.issues && step.issues.length > 0 && (
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-zinc-400">
              {step.issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          )}
        </>
      );
    case "Personalizer":
      return (
        <>
          <p className="text-zinc-400">
            {step.mode ? MODE_LABEL[step.mode] : ""} · {step.lang?.toUpperCase()}
            {step.summary ? ` · ${step.summary}` : ""}
          </p>
          {step.text && <Quote>{step.text}</Quote>}
        </>
      );
    case "Voice":
      return (
        <p className="text-zinc-400">
          {step.duration_s != null ? `Clip ${step.duration_s.toFixed(1)} s` : "No audio"}
          {step.style ? ` · ${step.style}` : ""}
          {step.summary ? ` · ${step.summary}` : ""}
        </p>
      );
    case "Template":
      return (
        <>
          <p className="text-zinc-400">
            {step.summary}
            {step.reason ? `, because ${REASON_LABEL[step.reason]}` : ""}
          </p>
          {step.text && <Quote>{step.text}</Quote>}
        </>
      );
  }
}

export function AgentTrace({ match, lineId }: { match: MatchData; lineId: string }) {
  const [trace, setTrace] = useState<Trace | null | undefined>(undefined);
  useEffect(() => {
    let live = true;
    setTrace(undefined);
    getTrace(lineId).then((tr) => live && setTrace(tr));
    return () => {
      live = false;
    };
  }, [lineId]);
  if (trace === undefined) return <p className="mt-2 text-sm text-zinc-500">Loading trace…</p>;
  if (trace === null) return <p className="mt-2 text-sm text-zinc-500">No trace for this line.</p>;
  const events = trace.events.map((id) => match.eventById.get(id)).filter((e) => e != null);
  return (
    <ol className="mt-2 space-y-2 border-l border-zinc-700 pl-3 text-sm" aria-label="How this line was made, step by step">
      {trace.steps.map((s, i) => (
        <li key={i} className="relative">
          <span className={`absolute -left-[15px] top-1.5 h-1.5 w-1.5 rounded-full ${s.fact_check === "fixed" ? "bg-amber-400" : "bg-zinc-400"}`} />
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-zinc-200">{s.agent}</span>
            {s.agent !== "Template" && s.fact_check && (
              <span className={`rounded px-1.5 py-px text-xs font-medium ${BADGE[s.fact_check] ?? BADGE.template}`}>
                {s.fact_check === "fixed" ? "Fixed" : s.fact_check === "removed" ? "Removed" : s.fact_check === "pass" ? "Passed" : s.fact_check}
              </span>
            )}
          </div>
          <StepDetails step={s} />
        </li>
      ))}
      {events.length > 0 && (
        <li className="text-zinc-500">
          Source events: {events.map((e) => `${e.type.replace(/_/g, " ")} ${minuteLabel(e.t)}`).join(", ")}
        </li>
      )}
    </ol>
  );
}
