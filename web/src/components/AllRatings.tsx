/**
 * All ratings tab: one vertical lineup pitch, Azure on top in 4-3-3, Redmond below in 4-4-2,
 * no names, a live rating pill overlapping the bottom edge of each dot. Click selects the player.
 * The slot layout is presentation only (the simulator's FORMATION_XY is not in the match files).
 */
import { useState } from "react";
import { useMatchTime } from "../hooks/useClock";
import { useSettings } from "../hooks/useSettings";
import { ratingColor, ratingTextColor } from "../lib/colors";
import { COLORS, KEEPER_COLORS } from "../lib/config";
import { ratingAt, type MatchData, type PlayerInfo } from "../lib/match";
import { ratingLabel } from "../lib/format";

const W = 68;
const H = 105;

const ROWS: { slots: string[] }[] = [
  { slots: ["GK"] },
  { slots: ["RB", "CB", "LB"] },
  { slots: ["RM", "DM", "CM", "AM", "LM"] },
  { slots: ["RW", "ST", "LW"] },
];

/** Order inside a row as the team sees it (right side first), center slots by shirt number. */
function rowPlayers(players: PlayerInfo[], slots: string[]): PlayerInfo[] {
  const rank = (p: PlayerInfo) => slots.indexOf(p.slot) * 100 + p.number;
  return players.filter((p) => slots.includes(p.slot)).sort((a, b) => rank(a) - rank(b));
}

function layout(match: MatchData): { p: PlayerInfo; x: number; y: number }[] {
  const out: { p: PlayerInfo; x: number; y: number }[] = [];
  const all = [...match.players.values()];
  const rowsY = { azc: [7, 19.5, 32, 44.5], rdm: [98, 85.5, 73, 60.5] };
  for (const team of ["azc", "rdm"] as const) {
    const players = all.filter((p) => p.team === team);
    ROWS.forEach((row, i) => {
      let ps = rowPlayers(players, row.slots);
      // Azure faces down the screen, so its right side is on the left; Redmond faces up.
      if (team === "rdm") ps = ps.reverse();
      ps.forEach((p, j) => out.push({ p, x: (W * (j + 1)) / (ps.length + 1), y: rowsY[team][i] }));
    });
  }
  return out;
}

/** Team name pill in the team's colour with its abbreviation, as on the score bar: "Azure City (AZC) 4-3-3". */
function TeamLabel({ team, className }: { team: MatchData["teams"]["azc"]; className?: string }) {
  return (
    <div className={`px-1 text-sm ${className ?? ""}`}>
      <span className="inline-block rounded px-2 py-0.5 font-medium text-white" style={{ background: team.color }}>
        {team.name} ({team.abbr}) <span className="font-normal text-white/80">{team.formation}</span>
      </span>
    </div>
  );
}

export function AllRatings({ match, onPick }: { match: MatchData; onPick: (id: string) => void }) {
  const t = useMatchTime(4);
  const { selected, colorblind } = useSettings();
  const spots = layout(match);
  const [focused, setFocused] = useState<string | null>(null);
  const line = { stroke: "rgba(255,255,255,0.55)", strokeWidth: 0.25, fill: "none" } as const;

  return (
    <section className="rounded-xl border border-white/5 bg-zinc-900/80 p-2">
      <TeamLabel team={match.teams.azc} className="mb-1" />
      <svg viewBox={`-2 -2 ${W + 4} ${H + 4}`} className="w-full" role="group" aria-label="All ratings lineup. Choose a player to follow.">
        <rect x={-2} y={-2} width={W + 4} height={H + 4} rx={2} fill={COLORS.pitch} />
        <rect x={0} y={0} width={W} height={H} {...line} />
        <line x1={0} x2={W} y1={H / 2} y2={H / 2} {...line} />
        <circle cx={W / 2} cy={H / 2} r={9.15} {...line} />
        <rect x={(W - 40.32) / 2} y={0} width={40.32} height={16.5} {...line} />
        <rect x={(W - 40.32) / 2} y={H - 16.5} width={40.32} height={16.5} {...line} />
        <rect x={(W - 18.32) / 2} y={0} width={18.32} height={5.5} {...line} />
        <rect x={(W - 18.32) / 2} y={H - 5.5} width={18.32} height={5.5} {...line} />
        {spots.map(({ p, x, y }) => {
          const team = match.teams[p.team];
          const r = ratingAt(match, p.id, t);
          const off = match.sentOff.get(p.id);
          const gone = off && t >= off.cardT;
          return (
            <g
              key={p.id}
              transform={`translate(${x} ${y})`}
              className="cursor-pointer outline-none"
              role="button"
              tabIndex={0}
              aria-pressed={p.id === selected}
              aria-label={`#${p.number} ${p.name}, ${team.name}, ${p.slot}, rating ${ratingLabel(r)}${gone ? ", sent off" : ""}`}
              onClick={() => onPick(p.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPick(p.id);
                }
              }}
              onFocus={() => setFocused(p.id)}
              onBlur={() => setFocused((f) => (f === p.id ? null : f))}
              opacity={gone ? 0.45 : 1}
            >
              {/* SVG elements don't draw a focus outline reliably, so keyboard focus gets its own ring */}
              {focused === p.id && <circle r={6} fill="none" stroke="#fff" strokeWidth={0.5} strokeDasharray="1.2 0.8" />}
              {p.id === selected && <circle r={5.1} fill="none" stroke={COLORS.lime} strokeWidth={0.5} />}
              <circle r={4.3} fill={p.isKeeper ? KEEPER_COLORS[p.team] : team.color} stroke="#fff" strokeWidth={0.3} />
              <text textAnchor="middle" dominantBaseline="central" fontSize={2.9} fontWeight={700} fill={p.isKeeper ? "#18181b" : "#fff"}>
                #{p.number}
              </text>
              <rect x={-3.2} y={3.1} width={6.4} height={3.2} rx={1.1} fill={ratingColor(r, colorblind)} />
              <text y={4.75} textAnchor="middle" dominantBaseline="central" fontSize={2.3} fontWeight={700} fill={ratingTextColor(r, colorblind)}>
                {ratingLabel(r)}
              </text>
              {gone && <rect x={3} y={-5} width={2} height={2.8} rx={0.3} fill="#EF4444" />}
            </g>
          );
        })}
      </svg>
      <TeamLabel team={match.teams.rdm} className="mt-1" />
    </section>
  );
}
