/** Right sidebar with the Player and All ratings tabs. */
import { useSettings } from "../hooks/useSettings";
import type { MatchData } from "../lib/match";
import { AllRatings } from "./AllRatings";
import { CommentaryPanel } from "./CommentaryPanel";
import { PlayerCard } from "./PlayerCard";
import { RatingLog } from "./RatingLog";

export type SidebarTab = "player" | "all";

interface Props {
  match: MatchData | null;
  tab: SidebarTab;
  setTab: (t: SidebarTab) => void;
  started: boolean;
  ended: boolean;
}

export function Sidebar({ match, tab, setTab, started, ended }: Props) {
  const { selected, select } = useSettings();
  return (
    <aside className="flex min-h-0 flex-col gap-2 overflow-y-auto bg-zinc-950 p-3 lg:h-full lg:py-4 lg:pl-0 lg:pr-4 lg:w-[360px] lg:shrink-0 xl:w-[400px]">
      <div className="grid grid-cols-2 gap-1 rounded-lg bg-zinc-900 p-1 text-sm" role="tablist" aria-label="Sidebar">
        {(
          [
            ["player", "Player"],
            ["all", "All ratings"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded-md py-1 ${tab === id ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-zinc-200"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {!match ? (
        <p className="p-3 text-sm text-zinc-500">Preparing match…</p>
      ) : tab === "player" ? (
        <>
          <PlayerCard match={match} player={selected} final={ended} />
          <CommentaryPanel match={match} player={selected} started={started} />
          <RatingLog match={match} player={selected} />
        </>
      ) : (
        <div className="min-h-0 overflow-y-auto">
          <AllRatings
            match={match}
            onPick={(id) => {
              select(id);
              setTab("player");
            }}
          />
        </div>
      )}
    </aside>
  );
}
