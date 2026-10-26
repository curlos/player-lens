/**
 * Dev/preview stand-in for the Phase 3 FastAPI routes that serve match data:
 *   GET /data/...   static files from the repo-root data/ folder (nothing is copied into web/)
 *   GET /matches    the match library list, shaped like the backend's response
 */
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";
import type { Connect, Plugin } from "vite";

const dataDir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "data");

// Mirrors LIBRARY in sim/library.py (the backup hero is deliberately left out of the picker).
const LIBRARY_IDS = ["md38_title_decider", "md19_blowout", "md27_draw"];

function listMatches() {
  return LIBRARY_IDS.map((id) => {
    const meta = JSON.parse(readFileSync(join(dataDir, "matches", id, "meta.json"), "utf8"));
    const [home, away] = meta.teams;
    return {
      match_id: meta.match_id,
      label: meta.label,
      blurb: meta.blurb ?? null,
      matchday: meta.matchday,
      home: home.abbr,
      away: away.abbr,
      score: meta.score,
      hero: meta.hero,
    };
  });
}

const middleware: Connect.NextHandleFunction = (req, res, next) => {
  const url = (req.url ?? "").split("?")[0];
  if (url === "/matches") {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify(listMatches()));
    return;
  }
  if (url.startsWith("/data/")) {
    let file = "";
    try {
      file = normalize(join(dataDir, decodeURIComponent(url.slice("/data/".length))));
    } catch {
      // malformed percent-escape: treated as not found below
    }
    if (!file || !file.startsWith(dataDir + sep) || !existsSync(file) || !statSync(file).isFile()) {
      res.statusCode = 404;
      res.end("not found");
      return;
    }
    res.setHeader("Content-Type", file.endsWith(".json") ? "application/json" : "application/octet-stream");
    // no-store in dev so regenerated matches show up on a plain reload (production uses long cache headers).
    res.setHeader("Cache-Control", "no-store");
    createReadStream(file).pipe(res);
    return;
  }
  next();
};

export function matchDataPlugin(): Plugin {
  return {
    name: "player-lens-match-data",
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}
