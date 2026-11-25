/* global d3, VApp, VC */
(function () {
  const A = VApp;
  const COLS = ["Technology", "Examiner", "Stage", "Ground"];
  let show = "frozen";

  function init() {
    d3.selectAll("input[name=vis4show]").on("change", e => { show = e.target.value; update(); });
  }

  function update() {
    const D = A.D, st = A.state;
    const base = A.brushRows(A.baseRows());
    const [off, on] = A.pairModels();
    let rows = D.slices.candidates.slice();
    if (show === "frozen") rows = rows.filter(r => A.frozenIds.includes(r.rule_id));
    else if (show === "eligible") rows = rows.filter(r => r.eligible);
    rows.sort((a, b) => (a.rank || 1e9) - (b.rank || 1e9) || b.search_ece_max - a.search_ece_max);

    const population = A.periodRows();
    const gAllOff = VC.gap(population, off), gAllOn = VC.gap(population, on);
    const live = rows.map(r => {
      const preds = A.rulePreds(r.rule_id);
      const m = base.filter(c => VC.matches(c, preds));
      return { r, n: m.length, fam: VC.families(m), gapOff: VC.gap(m, off) - gAllOff, gapOn: VC.gap(m, on) - gAllOn,
               eceOff: VC.ece(m, off, D.meta.n_bins), eceOn: VC.ece(m, on, D.meta.n_bins) };
    });
    const maxEce = d3.max(rows, r => r.search_ece_max) || 0.2;

    const body = d3.select("#vis4-body").html("");
    const ruleText = r => COLS.map(c => r.columns && r.columns[c]).filter(Boolean).join(" · ") || r.label;
    const t = body.append("table").attr("class", "grid");
    const hdr = t.append("thead").append("tr");
    hdr.append("th").text("Rank");
    hdr.append("th").text("Group (conditions)");
    hdr.append("th").attr("class", "num").attr("title", "families in 2014 part A (finds the groups) / part B (re-checks them)").text("Families A / B");
    hdr.append("th").attr("title", "the biggest ECE of the four models in 2014 part A: used to sort the groups").text("Biggest ECE");
    hdr.append("th").attr("class", "num").text("Group − population gap")
      .append("span").attr("class", "column-key").text(`${D.meta.short[off]} / ${D.meta.short[on]}`);

    const tb = t.append("tbody");
    const tr = tb.selectAll("tr").data(live).join("tr")
      .attr("class", d => "row" + (d.r.rule_id === st.slice ? " selected" : "") + (d.fam < D.meta.min_families ? " low" : ""))
      .on("click", (e, d) => A.set({ slice: st.slice === d.r.rule_id ? null : d.r.rule_id }))
      .on("mousemove", (e, d) => A.showTip(e,
        `<b>${d.r.label}</b><br>2014 part A: ${d.r.search_n_families} families, biggest ECE ` +
        `${A.fmt(d.r.search_ece_max)} (${A.modelLabel(d.r.search_ece_max_model) || d.r.search_ece_max_model})<br>` +
        `selected now: ${d.n} cases, ${d.fam} families; ECE off ${A.fmt(d.eceOff)}, on ${A.fmt(d.eceOn)}<br><i>click to select this group</i>` +
        (d.fam < D.meta.min_families ? "<br><i>fewer than 100 families here: too few to trust</i>" : "")))
      .on("mouseleave", A.hideTip);
    tr.append("td").text(d => A.frozenIds.includes(d.r.rule_id) ? `⚑${d.r.rank}` : (d.r.rank ?? "–"));
    tr.append("td").attr("class", "rule").append("button").attr("type", "button").attr("class", "rule-button")
      .attr("aria-pressed", d => String(d.r.rule_id === st.slice)).text(d => ruleText(d.r));
    tr.append("td").attr("class", "num").text(d => `${d.r.search_n_families} / ${d.r.assess_n_families}`);
    tr.append("td").each(function (d) {
      const cell = d3.select(this);
      const width = 36;
      cell.append("svg").attr("viewBox", `0 0 ${width} 10`).attr("width", width).attr("aria-hidden", "true")
        .append("rect").attr("width", width * d.r.search_ece_max / maxEce).attr("height", 8).attr("y", 1).attr("fill", "#8c8c8c");
      cell.append("span").text(" " + A.fmt(d.r.search_ece_max));
    });
    tr.append("td").attr("class", "num").html(d => chip(d.gapOff) + " " + chip(d.gapOn));
    body.attr("data-mode", show);
    if (!rows.length) body.append("p").attr("class", "muted").text("No groups in this list.");
    laterChart();
  }

  const PERIODS = [
    { key: "A", label: "14 A", long: "2014 part A", test: c => c.part === "dev_search" },
    { key: "B", label: "14 B", long: "2014 part B", test: c => c.part === "dev_assess" },
    { key: "2015", label: "2015", long: "2015", test: c => c.block === "test" && +c.year === 2015 },
    { key: "2016", label: "2016", long: "2016", test: c => c.block === "test" && +c.year === 2016 },
    { key: "2017", label: "2017", long: "2017", test: c => c.block === "test" && +c.year === 2017 },
  ];
  const RECHECKS = [
    ["B", "dev_assess", c => c.part === "dev_assess"],
    ["T", "test", c => c.block === "test"],
  ];

  function recheck(rows, id, part, matches, model) {
    const D = A.D;
    const report = A.state.cohort === "primary" && !D.meta.synthetic
      ? D.slices.assessment.find(row => row.part === part && row.rule_id === id) : null;
    if (report) {
      return { support: report.support_ok, pass: report.support_ok && report["pass_" + model],
        gap: report["gap_" + model] };
    }
    const group = rows.filter(matches);
    const gap = VC.gap(group, model);
    const support = VC.families(group) >= D.meta.min_families;
    if (!support) return { support, pass: false, gap };

    const { difference } = VC.familyBootstrap(rows, {
      difference: sample => VC.gap(sample.filter(matches), model) - VC.gap(sample, model),
    }, 500, 7);
    return { support, gap, pass: Math.abs(difference.est) >= D.meta.effect_min && (difference.lo > 0 || difference.hi < 0) };
  }

  const cache = {};
  function laterStats() {
    const D = A.D, st = A.state, [off, on] = A.pairModels();
    const key = st.cohort + "|" + st.pair;
    if (cache[key]) return cache[key];
    const all = D.cases.filter(c => st.cohort === "all" || c.primary === 1);
    const groups = [{ id: null, name: "full population" }].concat(A.frozenIds.map((id, i) => ({ id, name: `⚑${i + 1} ${A.ruleLabel(id)}` })));
    const out = groups.map(g => {
      const inG = g.id ? (c => VC.matches(c, A.rulePreds(g.id))) : (() => true);
      const pts = PERIODS.map((P, j) => {
        const rows = all.filter(c => P.test(c) && inG(c));
        if (rows.length < 5) return { P, n: rows.length, fam: VC.families(rows) };
        const bs = VC.familyBootstrap(rows, { off: r => VC.gap(r, off), on: r => VC.gap(r, on) }, 200, 11 + j);
        return { P, n: rows.length, fam: VC.families(rows), off: bs.off, on: bs.on };
      });
      const diffs = g.id ? Object.fromEntries(RECHECKS.map(([k, part, filter]) => [
        k, recheck(all.filter(filter), g.id, part, inG, off),
      ])) : null;
      return { ...g, pts, diffs };
    });
    cache[key] = out;
    return out;
  }

  function laterChart() {
    const [off, on] = A.pairModels();
    const box = d3.select("#vis4-later").html("");
    const answer = d3.select("#vis4-answer").html("");
    box.append("div").attr("class", "subhead").text("Gap per period · gray band marks 2014 part A");
    const S = laterStats();
    const vals = S.flatMap(g => g.pts.filter(p => p.off).flatMap(p => [p.off.est, p.on.est]));
    const lim = Math.min(0.3, Math.max(0.1, Math.ceil(((d3.max(vals, Math.abs) || 0.1) + 0.04) * 20) / 20));
    const grid = box.append("div").attr("class", "smallmult");
    const columns = getComputedStyle(grid.node()).gridTemplateColumns.split(" ").length;
    const w = Math.max(170, Math.floor((grid.node().clientWidth - 12 * (columns - 1)) / columns));
    const h = 124, m = { l: 34, r: 6, t: 30, b: 20 };
    const fullPop = S[0];
    S.forEach((g, gi) => {
      const svg = grid.append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h);
      const x = d3.scalePoint(PERIODS.map(p => p.key), [m.l + 12, w - m.r - 8]);
      const y = d3.scaleLinear([-lim, lim], [h - m.b, m.t]);
      svg.append("rect").attr("x", x("A") - 15).attr("width", 30).attr("y", m.t).attr("height", h - m.b - m.t).attr("fill", "#eee");
      svg.append("line").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(0)).attr("y2", y(0)).attr("stroke", "#bbb").attr("stroke-dasharray", "3 3");
      svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(3).tickFormat(d3.format("+.1f")));
      svg.append("g").attr("class", "axis").attr("transform", `translate(0,${h - m.b})`).call(d3.axisBottom(x).tickFormat(k => PERIODS.find(p => p.key === k).label).tickSize(2));
      svg.append("text").attr("x", 2).attr("y", 11).style("font-weight", 600).style("font-size", "10.5px").text(trunc(g.name, Math.floor(w / 5.6)));
      if (gi > 0) {
        const ev = fullPop.pts.filter(p => p.off);
        svg.append("path").datum(ev).attr("fill", "none").attr("stroke", "#999").attr("stroke-width", 1.2)
          .attr("d", d3.line().x(p => x(p.P.key)).y(p => y(p.off.est)));
        const { pass, support } = g.diffs.T;
        const status = !support ? "2015–17: few families" : pass ? "2015–17: threshold met" : "2015–17: threshold unmet";
        svg.append("text").attr("x", 2).attr("y", 24).style("font-size", "10px").style("font-weight", pass ? 700 : 400)
          .style("fill", pass ? "#b42318" : "#777").text(status);
      } else {
        svg.append("text").attr("x", 2).attr("y", 24).style("font-size", "10px").style("fill", "#777").text("for comparison (gray line in the others)");
      }
      [["off", off, -3], ["on", on, 3]].forEach(([k, mod, dx]) => {
        const pts = g.pts.filter(p => p[k]);
        svg.append("path").datum(pts).attr("fill", "none").attr("stroke", A.color(mod)).attr("stroke-width", 1.6)
          .attr("d", d3.line().x(p => x(p.P.key) + dx).y(p => y(p[k].est)));
        for (const p of pts) {
          if (Number.isFinite(p[k].lo) && Number.isFinite(p[k].hi)) {
            svg.append("line").attr("x1", x(p.P.key) + dx).attr("x2", x(p.P.key) + dx)
              .attr("y1", y(Math.max(-lim, p[k].lo))).attr("y2", y(Math.min(lim, p[k].hi)))
              .attr("stroke", A.color(mod)).attr("stroke-opacity", 0.55);
          }
          svg.append("circle").attr("cx", x(p.P.key) + dx).attr("cy", y(p[k].est)).attr("r", 3).attr("fill", A.color(mod))
            .on("mousemove", e => A.showTip(e, `<b>${g.name}</b><br>${p.P.long}, ${A.modelLabel(mod)}<br>` +
              `gap ${A.fmtSigned(p[k].est)} (95% CI ${A.fmtSigned(p[k].lo, 2)} to ${A.fmtSigned(p[k].hi, 2)})<br>${p.n} cases, ${p.fam} families`))
            .on("mouseleave", A.hideTip);
        }
      });
    });
    box.append("div").attr("class", "note").html(`<span style="color:${A.color(off)}">●</span> ${A.modelLabel(off)} &nbsp; ` +
      `<span style="color:${A.color(on)}">●</span> ${A.modelLabel(on)} &nbsp; <span style="color:#999">—</span> full population gap ` +
      `&nbsp; · up = gap (predicted − real allowance), bars = 95% CI. Threshold labels refer to profile off.`);
    const fl = S.slice(1);
    if (!fl.length) {
      answer.append("p").attr("class", "answer").text("No groups were flagged in this export.");
      return;
    }
    const ids = k => fl.map((g, i) => g.diffs[k].pass ? "⚑" + (i + 1) : null).filter(Boolean);
    const T = ids("T"), B = ids("B");
    const both = B.filter(flag => T.includes(flag));
    const own = fl.map(g => g.diffs.T.gap * 100).filter(Number.isFinite);
    // Jaccard overlap is measured on the 2014 discovery cases.
    const st = A.state, partA = A.D.cases.filter(c => c.part === "dev_search" && (st.cohort === "all" || c.primary === 1));
    const sets = A.frozenIds.map(id => new Set(partA.filter(c => VC.matches(c, A.rulePreds(id))).map(c => c.id)));
    const jac = (x, y) => { let n = 0; for (const v of x) if (y.has(v)) n++; return n / (x.size + y.size - n || 1); };
    const comp = sets.map((_, i) => i);
    const find = i => comp[i] === i ? i : (comp[i] = find(comp[i]));
    const pairJ = [];
    for (let i = 0; i < sets.length; i++) for (let j = i + 1; j < sets.length; j++) {
      const v = jac(sets[i], sets[j]); if (v >= 0.5) { comp[find(i)] = find(j); pairJ.push([i, j, v]); }
    }
    const clusters = d3.groups(sets.map((_, i) => i), i => find(i)).map(([, m]) => m).filter(m => m.length > 1);
    const overlap = clusters.map(m => {
      const js = pairJ.filter(([i, j]) => m.includes(i) && m.includes(j)).map(x => x[2]);
      const lo = Math.round(d3.min(js) * 100), hi = Math.round(d3.max(js) * 100);
      return `${m.map(i => "⚑" + (i + 1)).join(", ")} (Jaccard overlap ${lo === hi ? lo : lo + "–" + hi}%)`;
    });
    const counts = flags => `${flags.length} of ${fl.length}${flags.length ? " (" + flags.join(", ") + ")" : ""}`;
    const headline = both.length ? `${counts(both)} passed both re-checks` : "No group passed both re-checks";
    const ownGap = own.length
      ? ` The groups' own 2015–2017 gaps range from ${A.fmtSigned(d3.min(own), 1)} to ${A.fmtSigned(d3.max(own), 1)} percentage points.` : "";
    answer.append("p").attr("class", "answer").html(
      `<b>Answer (${A.modelLabel(off)}) · ${headline}.</b> ` +
      `The relative-gap threshold was met by ${counts(B)} in 2014 part B and ${counts(T)} in 2015–2017.` + ownGap +
      (overlap.length ? ` Overlap in 2014 part A: ${overlap.join("; ")}.` : "") +
      (st.cohort === "all" || A.D.meta.synthetic ? " Re-checks use live estimates for this dataset." : ""));
  }
  function trunc(t, n) { return t.length > n ? t.slice(0, n - 1) + "…" : t; }

  function chip(v) {
    if (Number.isNaN(v)) return "–";
    const c = d3.scaleDiverging([0.15, 0, -0.15], d3.interpolateRdBu)(Math.max(-0.15, Math.min(0.15, v)));
    const txt = Math.abs(v) > 0.09 ? "#fff" : "#1d1d1b";
    return `<span class="gap-value" style="background:${c};color:${txt};padding:0 4px;border-radius:3px">${A.fmtSigned(v, 2)}</span>`;
  }

  VApp.views.vis4 = { init, update };
})();
