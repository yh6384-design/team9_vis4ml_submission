/* global d3, VApp, VC */
(function () {
  const A = VApp;

  function init() {}

  function mode(rows, k) {
    const r = d3.rollups(rows, v => v.length, c => String(c[k]));
    return r.length ? d3.greatest(r, x => x[1])[0] : null;
  }

  function ladder(period) {
    const st = A.state, D = A.D;
    const f0 = { ...st.filters };
    if (!A.anyCaseFilter() && !st.slice && !st.brush) {
      const out = [{ label: "Full population of this period", patch: {}, full: { ...f0 }, key: "all" }];
      const tcs = d3.rollups(period, v => v.length, c => String(c.tc))
        .filter(([t]) => t && t !== "other" && t !== "null").sort((a, b) => d3.descending(a[1], b[1]));
      for (const [t, n] of tcs) if (n >= (D.meta.view_min_cases || 30)) out.push({ label: `Tech center ${t}`, full: { ...A.noFilters(), tc: t }, key: "tc" + t });
      return out;
    }
    const steps = [{ label: "Current selection", patch: {} }];
    let cur = {}, au = null, tc = null;
    const val = k => (k in cur ? cur[k] : f0[k]);
    if (f0.examiner !== "all") {
      const exRows = period.filter(c => c.examiner === f0.examiner);
      au = mode(exRows, "art_unit"); tc = mode(exRows, "tc");
    }
    if (val("ex_group") !== "all" || f0.examiner !== "all") {
      const a = val("art_unit") !== "all" ? val("art_unit") : (au || "all");
      cur = { ...cur, examiner: "all", ex_group: "all", art_unit: a };
      steps.push({ label: a !== "all" ? `Same, any examiner in art unit ${a}` : "Same, any examiner", patch: { ...cur } });
    }
    if (val("art_unit") !== "all") {
      const t = val("tc") !== "all" ? val("tc") : (tc || String(val("art_unit")).slice(0, 2) + "00");
      cur = { ...cur, art_unit: "all", tc: t };
      steps.push({ label: `Same, any art unit in tech center ${t}`, patch: { ...cur } });
    }
    if (val("tc") !== "all") {
      cur = { ...cur, tc: "all" };
      steps.push({ label: "Same, all technologies", patch: { ...cur } });
    }
    steps.push({ label: "Full population of this period", patch: A.noFilters(), population: true });
    const out = [];
    for (const s of steps) {
      const full = { ...f0, ...s.patch };
      const key = JSON.stringify(full);
      if (out.at(-1)?.key === key && !(s.population && (st.slice || st.brush))) continue;
      out.push({ ...s, full, key });
    }
    return out;
  }

  function stats(rows, models) {
    const n = rows.length, k = d3.sum(rows, c => c.y);
    const [lo, hi] = VC.wilson(k, n);
    const o = { n, k, fam: VC.families(rows), obs: n ? k / n : NaN, lo, hi };
    for (const m of models) o[m] = n ? d3.mean(rows, c => c[m]) : NaN;
    return o;
  }

  function update() {
    const D = A.D, st = A.state;
    const models = A.pairModels();
    const minN = D.meta.view_min_cases || 30;
    const period = A.periodRows();
    const selected = A.brushRows(A.sliceRows(period));
    const steps = ladder(period).map(s => ({
      ...s, ...stats(s.population ? period : selected.filter(c => A.passes(c, s.full)), models),
    }));
    const body = d3.select("#vis1-body").html("");
    const W = Math.max(280, Math.round(body.node().getBoundingClientRect().width));
    const compact = W < 520;
    const rowH = compact ? 54 : 38;
    const M = { l: compact ? 16 : 204, r: compact ? 16 : 145, t: 4, b: 36 };

    if (st.filters.examiner !== "all") {
      const exRows = period.filter(c => c.examiner === st.filters.examiner);
      const e = (D.meta.examiners || {})[st.filters.examiner] || {};
      const g = e.group !== undefined ? e.group : +mode(exRows, "ex_group");
      const cut = D.meta.ex_group_cutoff || "2015-01-01";
      const pct = (k, n) => n ? Math.round(100 * k / n) + "%" : "–";
      const month = d => d ? new Date(d + "T00:00:00").toLocaleString("en-US", { month: "short", year: "numeric" }) : "";
      const card = body.append("div").attr("class", "card");
      card.append("strong").text(`Examiner ID ${st.filters.examiner}`);
      card.append("span").text(` · art unit ${e.art_unit || mode(exRows, "art_unit") || "–"}`);
      card.append("div").text(`Full record (retrospective): ${e.full_allowances ?? "–"} allowances in ` +
        `${e.full_decisions ?? "–"} decisions (${pct(e.full_allowances, e.full_decisions)}), ${month(e.first)} to ${month(e.last)}`);
      if (A.examinerGroupEnabled()) {
        card.append("div").text(`Examiner group: ${((D.meta.ex_groups || {})[g] || "G" + g).split(":")[0]} · ` +
          `${e.before_allowances ?? 0} allowances in ${e.before_decisions ?? 0} decisions mailed before ${cut}`);
      }
      card.append("div").attr("class", "muted").text(`${exRows.length} cases in ${D.meta.parts[st.part]}`);
    }

    const legend = body.append("div").attr("class", "chart-legend");
    models.forEach((m, i) => {
      const item = legend.append("span").attr("class", "legend-item");
      item.append("span").attr("class", "legend-mark").attr("aria-hidden", "true").style("--mark", A.color(m));
      item.append("span").text(i ? "Predicted, profile on" : "Predicted, profile off");
    });
    const observed = legend.append("span").attr("class", "legend-item");
    observed.append("span").attr("class", "legend-mark diamond").attr("aria-hidden", "true");
    observed.append("span").text("Real allowance (95% CI)");

    const H = M.t + steps.length * rowH + M.b;
    const x = d3.scaleLinear([0, 1], [M.l, W - M.r]);
    const svg = body.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", W).attr("height", H);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - M.b})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format(".0%")));
    svg.append("text").attr("x", (M.l + W - M.r) / 2).attr("y", H - 4).attr("text-anchor", "middle")
      .text("Allowance probability");
    for (const t of [0.25, 0.5, 0.75]) svg.append("line").attr("x1", x(t)).attr("x2", x(t)).attr("y1", M.t - 6)
      .attr("y2", H - M.b).attr("stroke", "#eee");
    const first = steps.findIndex(s => s.n >= minN);
    steps.forEach((s, i) => {
      const top = M.t + i * rowH;
      const y0 = top + (compact ? 40 : 15), few = s.n < minN, ink = few ? "#657485" : null;
      const choose = () => {
        if (s.population) A.views.vis2.clearBrush();
        A.set(s.population ? { filters: A.noFilters(), slice: null, brush: null } : { filters: { ...s.full } });
      };
      const g = svg.append("g").attr("class", "case-ladder").attr("role", "button").attr("tabindex", 0)
        .attr("aria-label", s.label).style("cursor", "pointer")
        .on("click", choose)
        .on("keydown", event => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); }
        })
        .on("mousemove", e => A.showTip(e, `<b>${s.label}</b>${s.sub ? "<br>" + s.sub : ""}<br>` +
          `${s.n} cases, ${s.fam} families; allowed ${s.k} = real allowance ${A.fmt(s.obs * 100, 0)}% (95% CI ${A.fmt(s.lo * 100, 0)}–${A.fmt(s.hi * 100, 0)}%)<br>` +
          models.map(m => `${A.modelLabel(m)}: predicted allowance ${A.fmt(s[m] * 100, 0)}%`).join("<br>") +
          (few ? `<br><i>fewer than ${minN} cases: the range is wide, read the next row down</i>` : "") +
          "<br><i>click to use these filters</i>"))
        .on("mouseleave", A.hideTip);
      g.append("rect").attr("x", 1).attr("y", top).attr("width", W - 2).attr("height", rowH - 3)
        .attr("fill", i === first ? "#edf5f8" : i % 2 ? "#f8fafb" : "transparent");
      g.append("text").attr("x", 6).attr("y", top + 14).style("fill", ink).style("font-weight", i === first ? 700 : 400)
        .text(trunc(s.label, compact ? Math.floor((W - 12) / 6.1) : 32));
      const support = few ? `${s.n} cases · low support` : `${s.n} cases · ${s.fam} families`;
      const preds = models.map(m => A.fmt(s[m] * 100, 0) + "%").join(" / ");
      const real = `${A.fmt(s.obs * 100, 0)}%`;
      g.append("text").attr("x", 6).attr("y", top + 28).style("fill", "#4f6275").style("font-size", "10.5px")
        .text(compact && s.n ? `Off / on ${preds} · Real ${real} · ${support}` : support);
      if (!s.n) return;
      g.append("line").attr("x1", x(s.lo)).attr("x2", x(s.hi)).attr("y1", y0).attr("y2", y0)
        .attr("stroke", few ? "#bbb" : "#1d1d1b").attr("stroke-width", 2);
      for (const m of models) {
        g.append("line").attr("x1", x(s[m])).attr("x2", x(s.obs)).attr("y1", y0).attr("y2", y0)
          .attr("stroke", few ? "#ccc" : A.color(m)).attr("stroke-opacity", 0.5).attr("stroke-width", 3);
      }
      models.forEach((m, j) => g.append("circle").attr("cx", x(s[m])).attr("cy", y0 + (j ? 3 : -3)).attr("r", 5)
        .attr("fill", few ? "#c8c8c8" : A.color(m)).attr("stroke", "#fff"));
      g.append("path").attr("d", d3.symbol(d3.symbolDiamond, 70)()).attr("transform", `translate(${x(s.obs)},${y0})`)
        .attr("fill", few ? "#9a9a9a" : "#1d1d1b");
      if (!compact) {
        g.append("text").attr("x", W - M.r + 8).attr("y", top + 14).style("fill", ink)
          .text(`Predicted ${preds}`);
        g.append("text").attr("x", W - M.r + 8).attr("y", top + 28).style("fill", ink)
          .text(`Real ${real} (${s.k} of ${s.n})`);
      }
    });

    const s = steps[first >= 0 ? first : steps.length - 1];
    if (s && s.n) {
      const [off, on] = models;
      const worse = Math.abs(s[on] - s.obs) < Math.abs(s[off] - s.obs) ? "closer" : "not closer";
      const none = !A.anyCaseFilter() && !st.slice && !st.brush;
      body.append("p").attr("class", "answer").html(
        `<b>Answer (${none ? "full population" : s.label.toLowerCase()}):</b> predicted allowance ${A.fmt(s[off] * 100, 0)}% (off) / ` +
        `${A.fmt(s[on] * 100, 0)}% (on); real allowance ${A.fmt(s.obs * 100, 0)}% (95% CI ${A.fmt(s.lo * 100, 0)}–${A.fmt(s.hi * 100, 0)}%). ` +
        `Profile on is <b>${worse}</b> to the real allowance.` +
        (none ? ` <span class="muted">Click a tech center, or choose your examiner in “Your case”.</span>` : ""));
    }
  }
  function trunc(t, n) { return t.length > n ? t.slice(0, n - 1) + "…" : t; }

  VApp.views.vis1 = { init, update };
})();
