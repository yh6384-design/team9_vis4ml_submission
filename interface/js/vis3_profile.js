/* global d3, VApp, VC */
(function () {
  const A = VApp;
  let metric = "auroc", split = "hist";
  let W = 440, rowH = 58; const M = { l: 146, r: 84, t: 26, b: 34 };
  const MEASURE = {
    auroc: { name: "AUROC", axis: "AUROC: higher is better, 0.5 = coin flip", better: +1 },
    ece: { name: "ECE", axis: "ECE: lower is better", better: -1 },
    gap: { name: "gap", axis: "Gap: predicted − real (0 is best)", better: 0 },
    brier: { name: "Brier score", axis: "Brier score: lower is better", better: -1 },
    logloss: { name: "log loss", axis: "log loss: lower is better", better: -1 },
  };

  function init() {
    d3.selectAll("input[name=vis3metric]").on("change", e => { metric = e.target.value; update(); });
    d3.selectAll("input[name=vis3split]").on("change", e => { split = e.target.value; update(); });
  }

  function fn(m) {
    if (metric === "auroc") return s => VC.auroc(s, m);
    if (metric === "ece") return s => VC.ece(s, m, A.D.meta.n_bins);
    if (metric === "brier") return s => VC.brier(s, m);
    if (metric === "logloss") return s => VC.logloss(s, m);
    return s => VC.gap(s, m);
  }

  function groupsOf(rows) {
    const D = A.D;
    const out = [{ label: "all selected cases", rows }];
    if (split === "hist") {
      D.meta.tiers.forEach((t, i) => out.push({ label: `history ${t} decisions`, rows: rows.filter(c => c.hist_tier === i) }));
    } else if (split === "round") {
      for (const r of [1, 2, 3]) out.push({ label: `round ${r === 3 ? "3+" : r}`, rows: rows.filter(c => +c.round_c === r) });
    } else {
      const tcs = d3.rollups(rows, v => v.length, c => String(c.tc)).sort((a, b) => d3.descending(a[1], b[1]));
      const big = tcs.filter(([t, n]) => n >= 20 && t !== "other").map(([t]) => t);
      for (const t of big) out.push({ label: `tech center ${t}`, rows: rows.filter(c => String(c.tc) === t) });
      const rest = rows.filter(c => !big.includes(String(c.tc)));
      if (rest.length) out.push({ label: "all other tech centers", rows: rest });
    }
    return out;
  }

  function rocChart(body, rows, off, on, maxS = 300) {
    const m = { l: 51, r: 16, t: 26, b: 38 };
    const S = Math.max(180, Math.min(maxS, Math.round(body.node().getBoundingClientRect().width) - m.l - m.r));
    const svg = body.append("svg").attr("viewBox", `0 0 ${S + m.l + m.r} ${S + m.t + m.b}`).attr("width", S + m.l + m.r).attr("height", S + m.t + m.b);
    const out = S + m.t + m.b;
    const x = d3.scaleLinear([0, 1], [m.l, m.l + S]), y = d3.scaleLinear([0, 1], [m.t + S, m.t]);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${m.t + S})`).call(d3.axisBottom(x).ticks(5).tickFormat(d3.format(".0%")));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d3.format(".0%")));
    svg.append("text").attr("x", m.l + S / 2).attr("y", m.t + S + 31).attr("text-anchor", "middle")
      .text("false positive rate");
    svg.append("text").attr("x", 2).attr("y", 12).style("font-weight", 600).text("ROC curve");
    svg.append("text").attr("transform", `translate(11,${m.t + S / 2}) rotate(-90)`).attr("text-anchor", "middle")
      .text("true positive rate");
    svg.append("line").attr("class", "diag").attr("x1", x(0)).attr("y1", y(0)).attr("x2", x(1)).attr("y2", y(1));
    const legend = svg.append("g").attr("transform", `translate(${m.l + S * 0.42},${m.t + S * 0.62})`);
    [off, on].forEach((k, i) => {
      const pts = VC.roc(rows, k), a = VC.auroc(rows, k);
      if (pts.length) svg.append("path").datum(pts).attr("fill", "none").attr("stroke", A.color(k)).attr("stroke-width", 2)
        .attr("d", d3.line().x(d => x(d[0])).y(d => y(d[1])));
      const g = legend.append("g").attr("transform", `translate(0,${i * 17})`);
      g.append("line").attr("x1", 0).attr("x2", 14).attr("y1", -4).attr("y2", -4).attr("stroke", A.color(k)).attr("stroke-width", 3);
      g.append("text").attr("x", 19).attr("y", 0).text(`${i ? "on" : "off"}: AUROC ${A.fmt(a, 3)}`);
    });
    legend.append("text").attr("x", 0).attr("y", 36).style("fill", "#888").style("font-size", "10px")
      .text("dashed = coin flip");
    return out;
  }

  function difference(off, on) {
    return { est: on.est - off.est, ...VC.interval(on.draws.map((value, i) => value - off.draws[i])) };
  }

  function summarize(outer, rows, off, on) {
    const { part, cohort, slice, brush } = A.state;
    const D = A.D;
    const report = part === "test" && !slice && !brush && !A.anyCaseFilter()
      ? D.e2.find(row => row.cohort === cohort && row.group_type === "all" &&
          row.pair === `${off}->${on}` && row.n === rows.length)
      : null;
    const answer = outer.append("p").attr("class", "answer");
    answer.append("strong").text("Answer · ");
    if (!rows.length) {
      answer.append("span").text("No cases match the current selection.");
      return;
    }
    const low = VC.families(rows) < D.meta.min_families;
    const live = report ? null : VC.familyBootstrap(rows, {
      auroc_off: r => VC.auroc(r, off), auroc_on: r => VC.auroc(r, on),
      ece_off: r => VC.ece(r, off, D.meta.n_bins), ece_on: r => VC.ece(r, on, D.meta.n_bins),
    });
    const messages = ["auroc", "ece"].map(key => {
      const label = key.toUpperCase();
      const left = report ? report[key + "_off"] : live[key + "_off"].est;
      const right = report ? report[key + "_on"] : live[key + "_on"].est;
      if (!Number.isFinite(left) || !Number.isFinite(right)) return label + " unavailable (both outcomes are required)";
      const delta = report ? {
        est: report["delta_" + key], lo: report["delta_" + key + "_lo"], hi: report["delta_" + key + "_hi"],
      } : difference(live[key + "_off"], live[key + "_on"]);
      const change = Number.isFinite(delta.lo) && Number.isFinite(delta.hi)
        ? `${A.fmtSigned(delta.est)}, 95% CI ${A.fmtSigned(delta.lo)} to ${A.fmtSigned(delta.hi)}`
        : A.fmtSigned(delta.est);
      const direction = key === "auroc" ? 1 : -1;
      let status = "";
      if (!low && Number.isFinite(delta.lo) && Number.isFinite(delta.hi)) {
        if (direction * delta.lo > 0 && direction * delta.hi > 0) status = " · improves";
        else if (direction * delta.lo < 0 && direction * delta.hi < 0) status = " · worsens";
        else status = " · difference inconclusive";
      }
      return `${label} ${A.fmt(left)} → ${A.fmt(right)} (on − off ${change})${status}`;
    });
    answer.append("span").text(messages.join(". ") + ".");
    answer.append("span").attr("class", "note").text(report ? " Experiment 2." : " Live selection.");
    if (low) answer.append("strong").text(` Fewer than ${D.meta.min_families} families. Descriptive only.`);
  }

  function update() {
    const D = A.D;
    const rows = A.selectedRows();
    const [off, on] = A.pairModels();
    const outer = d3.select("#vis3-body").html("");
    const narrow = outer.node().getBoundingClientRect().width < 660;
    const wrap = outer.append("div").attr("class", narrow ? "stack3" : "split3");
    const rocH = rocChart(wrap.append("div"), rows, off, on, narrow ? 215 : 255);
    const body = wrap.append("div");
    W = Math.max(360, Math.round(body.node().getBoundingClientRect().width));
    const groups = groupsOf(rows);
    for (const g of groups) {
      g.fam = VC.families(g.rows);
      if (g.rows.length < 5) { g.ok = false; continue; }
      const bs = VC.familyBootstrap(g.rows, { off: fn(off), on: fn(on) }, 200, 7);
      if (Number.isNaN(bs.off.est) || Number.isNaN(bs.on.est)) { g.ok = false; continue; }
      g.off = bs.off; g.on = bs.on;
      g.delta = difference(bs.off, bs.on);
      g.ok = true;
    }
    const vals = groups.filter(g => g.ok).flatMap(g => [g.off.est, g.off.lo, g.off.hi, g.on.est, g.on.lo, g.on.hi])
      .filter(Number.isFinite);
    let lo, hi;
    if (metric === "auroc") { lo = Math.min(0.5, d3.min(vals) ?? 0.5); hi = 1; }
    else if (metric === "gap") { lo = Math.min(-0.05, d3.min(vals) ?? 0); hi = Math.max(0.05, d3.max(vals) ?? 0); }
    else { lo = 0; hi = Math.max(0.02, d3.max(vals) || 0.1); }
    rowH = narrow ? 42 : Math.max(44, Math.min(72, Math.floor((rocH - M.t - M.b) / groups.length)));
    const H = M.t + groups.length * rowH + M.b;
    const x = d3.scaleLinear([lo, hi], [M.l, W - M.r]).nice();
    const svg = body.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", W).attr("height", H);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - M.b})`).call(d3.axisBottom(x).ticks(5));
    svg.append("text").attr("x", (M.l + W - M.r) / 2).attr("y", H - 2).attr("text-anchor", "middle").text(MEASURE[metric].axis);
    const ref = metric === "gap" ? 0 : metric === "auroc" ? 0.5 : null;
    if (ref !== null) svg.append("line").attr("x1", x(ref)).attr("x2", x(ref)).attr("y1", M.t).attr("y2", H - M.b).attr("stroke", "#bbb").attr("stroke-dasharray", "3 3");
    svg.append("text").attr("x", W - M.r + 6).attr("y", M.t - 8).style("fill", "#888").text("on − off");
    svg.append("text").attr("x", 2).attr("y", 12).style("font-weight", 600).text(MEASURE[metric].name + " by group");
    groups.forEach((g, i) => {
      const y0 = M.t + i * rowH + Math.round(rowH / 2) - 6;
      const low = g.fam < D.meta.min_families;
      svg.append("text").attr("x", 4).attr("y", y0 + 4).style("fill", low ? "#9a9a9a" : null).style("font-weight", i ? 400 : 700).text(g.label);
      svg.append("text").attr("x", 4).attr("y", y0 + 17).style("fill", "#888").style("font-size", "10px")
        .text(`${g.rows.length} cases · ${g.fam} families${low ? " (few)" : ""}`);
      if (!g.ok) {
        svg.append("text").attr("x", M.l).attr("y", y0 + 4).style("fill", "#9a9a9a")
          .text(g.rows.length < 5 ? "Too few cases" : "Requires both outcomes");
        return;
      }
      for (const [k, m, dy] of [["off", off, -5], ["on", on, 7]]) {
        const s = g[k];
        if (Number.isFinite(s.lo) && Number.isFinite(s.hi)) {
          svg.append("line").attr("x1", x(s.lo)).attr("x2", x(s.hi)).attr("y1", y0 + dy).attr("y2", y0 + dy)
            .attr("stroke", low ? "#bbb" : A.color(m)).attr("stroke-width", 2);
        }
        svg.append("circle").attr("cx", x(s.est)).attr("cy", y0 + dy).attr("r", 4.5).attr("fill", low ? "#bbb" : A.color(m))
          .on("mousemove", e => A.showTip(e, `<b>${A.modelLabel(m)}</b> · ${g.label}<br>${MEASURE[metric].name} ${A.fmt(s.est)} ` +
            `(95% CI ${A.fmt(s.lo)} to ${A.fmt(s.hi)})<br>${g.rows.length} cases, ${g.fam} families`))
          .on("mouseleave", A.hideTip);
      }
      const d = g.delta, b = MEASURE[metric].better;
      const verdict = low || b === 0 ? null : (b * d.lo > 0 && b * d.hi > 0) ? "better" : (b * d.lo < 0 && b * d.hi < 0) ? "worse" : null;
      svg.append("text").attr("x", W - M.r + 6).attr("y", y0 + 2)
        .style("fill", verdict === "better" ? "#1a7f37" : verdict === "worse" ? "#b42318" : "#555")
        .text(A.fmtSigned(d.est) + (verdict ? (verdict === "better" ? " better" : " worse") : ""));
      if (Number.isFinite(d.lo) && Number.isFinite(d.hi)) {
        svg.append("text").attr("x", W - M.r + 6).attr("y", y0 + 14).style("fill", "#888").style("font-size", "10px")
          .text(`${A.fmtSigned(d.lo, 2)} to ${A.fmtSigned(d.hi, 2)}`);
      }
    });
    const leg = svg.append("g").attr("transform", `translate(${M.l + 12},${10})`);
    [[off, "off"], [on, "on"]].forEach(([m, t], i) => {
      leg.append("circle").attr("cx", i * 52).attr("cy", 0).attr("r", 4.5).attr("fill", A.color(m));
      leg.append("text").attr("x", i * 52 + 8).attr("y", 4).text(t);
    });
    summarize(outer, rows, off, on);
  }

  VApp.views.vis3 = { init, update };
})();
