"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import Candidates from "@/components/Candidates";
import LiveBadge from "@/components/LiveBadge";
import { useLive } from "@/lib/live";
import Timeline from "@/components/Timeline";
import { getEvents, getStatus, getTrend, getWindows, pause, resume } from "@/lib/api";
import { CANNOT_KNOW, STATE_TEXT, TIER1_BANNER, labelFor } from "@/lib/claims";
import { answered, noDataFraction, openCandidates, stateWord } from "@/lib/format";

export default function Dashboard() {
  const qc = useQueryClient();
  const live = useLive();
  const status = useQuery({ queryKey: ["status"], queryFn: getStatus });
  const windows = useQuery({ queryKey: ["windows"], queryFn: getWindows });
  const events = useQuery({ queryKey: ["events"], queryFn: getEvents });
  const trend = useQuery({ queryKey: ["trend"], queryFn: getTrend });
  const rows = windows.data ?? [];
  const ev = events.data ?? [];
  const unreachable = status.isError;

  return (
    <>
      <header>
        <h1 className="text-4xl font-bold text-yellow-300">PGuard</h1>
        <div role="status" aria-live="polite" className="my-2 border-4 border-yellow-300 p-3 text-2xl font-bold">
          {unreachable ? "PGuard is not watching: the engine cannot be reached." : status.data?.indicator.text ?? "Loading…"}
        </div>
        <p role="status" aria-live="assertive"><strong>{status.data?.watchdog.text ?? ""}</strong></p>
        <LiveBadge live={live} />
        <p>{TIER1_BANNER}</p>
        <p><em>{CANNOT_KNOW}</em></p>
        <button onClick={async () => { await pause(3600); await qc.invalidateQueries(); }}
                className="m-1 rounded border-4 border-white bg-yellow-300 px-4 py-2 font-bold text-black">
          Pause sensing (1 hour)
        </button>
        <button onClick={async () => { await resume(); await qc.invalidateQueries(); }}
                className="m-1 rounded border-4 border-white bg-yellow-300 px-4 py-2 font-bold text-black">Resume</button>
        <nav aria-label="Other views" className="mt-2"><Link className="underline" href="/room">Signal-path view</Link></nav>
      </header>
      <main id="main">
        <Candidates open={openCandidates(ev)} />
        <section aria-labelledby="h-raw" className="my-4 rounded border-2 border-white p-4">
          <h2 id="h-raw" className="text-2xl font-bold text-yellow-300">1. Raw measurements</h2>
          <p>No data in the last windows: {(noDataFraction(rows) * 100).toFixed(0)}%. A gap is never shown as calm.</p>
          <Timeline rows={rows} />
        </section>
        <section aria-labelledby="h-est" className="my-4 rounded border-2 border-white p-4">
          <h2 id="h-est" className="text-2xl font-bold text-yellow-300">2. Model estimates (unverified)</h2>
          <p>Why: {String(status.data?.last?.reason ?? "no decision yet")}</p>
          <ul>{rows.slice(-6).map((r) => <li key={r.t_start}>{stateWord(r.state)} (level {r.level})</li>)}</ul>
        </section>
        <section aria-labelledby="h-conf" className="my-4 rounded border-2 border-white p-4">
          <h2 id="h-conf" className="text-2xl font-bold text-yellow-300">3. Confirmed or answered by a person</h2>
          <ul>
            {answered(ev).length === 0 ? <li>None yet.</li> :
              answered(ev).map((e) => <li key={e.id}>#{e.id} {labelFor(e.kind)}: {STATE_TEXT[e.state]}</li>)}
          </ul>
        </section>
        {trend.data?.enabled && (
          <section aria-labelledby="h-tr" className="my-4 rounded border-2 border-white p-4">
            <h2 id="h-tr" className="text-2xl font-bold text-yellow-300">4. Your trends (you opted in)</h2>
            <p>{trend.data.text}</p><p><em>{trend.data.disclaimer}</em></p>
          </section>
        )}
      </main>
    </>
  );
}
