// The ranking view: a score bar per airport, drawn from a rank_airports or compare_airports
// result. The bar's widths and labels come from the tool's points only, never the model's text.
// Loaded before app.js (see index.html), which calls rankingView when such a result arrives.
"use strict";

const STRAIN = ["delay", "cancellations", "fare premium"];

function pointsOf(row, label) {
  const signal = row.signals[label];
  return signal && typeof signal.points === "number" ? signal.points : 0;
}

function rankingView(name, result) {
  const box = el("section", { class: "ranking" });
  const where = result.region ? ` in ${result.region}` : "";
  box.append(el("h3", { text: `Ranking${where}, ${result.preset} preset` }));
  box.append(
    el("div", { class: "legend" },
      el("span", {}, el("span", { class: "key strain" }), "Strain (delay, cancellations, fares)"),
      el("span", {}, el("span", { class: "key growth" }), "Growth"),
      el("span", {}, el("span", { class: "key friction" }), "Friction penalty"),
    ),
  );
  for (const row of result.rows) {
    const strainParts = STRAIN.map((label) => [label, row.signals[label]]);
    const strain = STRAIN.reduce((sum, label) => sum + pointsOf(row, label), 0);
    const growth = pointsOf(row, "growth");
    const penalty = row.friction.points || 0;
    // Widths only: the bar is drawn from the tool's points; the labels quote the tool's numbers.
    const bar = el("div", { class: "bar", role: "img" });
    const strainSeg = el("span", { class: "seg strain" });
    const growthSeg = el("span", { class: "seg growth" });
    strainSeg.style.width = `${strain}%`;
    growthSeg.style.width = `${growth}%`;
    bar.append(strainSeg, growthSeg);
    if (penalty > 0) {
      const frictionSeg = el("span", { class: "seg friction" });
      // The hatched part covers the points the penalty took: from the score up to the score
      // before friction (shorter than the penalty when the score stopped at 0).
      frictionSeg.style.left = `${Math.max(row.score, 0)}%`;
      frictionSeg.style.width = `${Math.max(row.score_before_friction - row.score, 0)}%`;
      bar.append(frictionSeg);
    }
    const strainText = strainParts
      .map(([label, s]) => `${label} ${s && "points" in s ? s.points : "missing"}`)
      .join(", ");
    const stale = row.friction.stale ? `, ${row.friction.stale_note}` : "";
    const frictionText = penalty ? `−${penalty} (${row.friction.name}${stale})` : "none";
    bar.setAttribute(
      "aria-label",
      `${row.code}: score ${row.score}. Strain points: ${strainText}. ` +
        `Growth points: ${row.signals.growth?.points ?? "missing"}. Friction penalty: ${frictionText}.`,
    );
    const head = el("span", {}, el("b", { text: row.code }), ` ${row.name}`);
    if (row.confidence === "Low") {
      head.append(el("span", { class: "flag", text: "Low confidence", title: (row.confidence_reasons || []).join("; ") }));
    }
    box.append(
      el("div", { class: "airport" },
        el("span", { class: "rank", text: `${row.rank}` }),
        head,
        el("span", { class: "score", text: `${row.score}` }),
        bar,
        el("span", {
          class: "parts",
          text: `Strain ${strainText} · Growth ${row.signals.growth?.points ?? "missing"} · ` +
            `Friction ${frictionText} · National rank ${row.national_rank} of ${result.ranked_count}`,
        }),
      ),
    );
  }
  if (result.not_ranked?.length) {
    const list = result.not_ranked.map((n) => `${n.code} (${n.reason})`).join("; ");
    box.append(el("p", { class: "not-ranked", text: `Not ranked: ${list}` }));
  }
  return box;
}
