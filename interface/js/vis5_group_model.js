/* global d3, VApp, VC */
(function () {
  const A = VApp;
  let metric = "rel", more = false;

  function init() {
    d3.selectAll("input[name=vis5metric]").on("change", e => { metric = e.target.value; update(); });
    d3.select("#vis5-more").on("change", e => { more = e.target.checked; update(); });
  }

  function update() {
    const D = A.D, st = A.state;
    const base = A.brushRows(A.baseRows());
    const models = D.meta.learned_models;
    const SEL = "__selection__";
    let ids = [SEL].concat(A.frozenIds);
    if (more) ids = ids.concat(D.slices.candidates.filter(c => c.eligible && !ids.includes(c.rule_id)).map(c => c.rule_id));
    const cells = [];
    const label = id => id === SEL ? "Your selection (all your filters)" : A.ruleLabel(id);
    const population = A.periodRows();
    const allGap = Object.fromEntries(models.map(k => [k, VC.gap(population, k)]));
    const rowsInfo = ids.map(id => {
      const m = id === SEL ? A.sliceRows(base) : base.filter(c => VC.matches(c, A.rulePreds(id)));
      const fam = VC.families(m);
      for (const k of models) {
        cells.push({ id, model: k, fam, n: m.length,
          v: metric === "gap" ? VC.gap(m, k) : metric === "rel" ? VC.gap(m, k) - allGap[k] : VC.ece(m, k, D.meta.n_bins),
          prev: VC.prevalence(m) });
      }
      return { id, fam, n: m.length };
    });
    const body = d3.select("#vis5-body").html("");
    const avail = Math.max(348, Math.round(body.node().getBoundingClientRect().width));
    const rh = 38, lw = Math.min(268, Math.round(avail * 0.4)), top = 30;
    const cw = Math.min(110, Math.floor((avail - lw - 10) / models.length));
    const W = lw + cw * models.length + 10, H = top + rh * ids.length + 46;
    const svg = body.append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("width", W).attr("height", H);
    const maxAbs = Math.max(0.05, d3.max(cells.filter(c => c.fam >= D.meta.min_families), c => Math.abs(c.v)) || 0.05);
    const lim = Math.ceil(maxAbs * 20) / 20;
    const div = metric !== "ece";
    const col = div ? d3.scaleDiverging([lim, 0, -lim], d3.interpolateRdBu)
                                 : d3.scaleSequential([0, lim], d3.interpolateBlues);
    models.forEach((k, j) => {
      const isPair = A.pairModels().includes(k);
      svg.append("text").attr("x", lw + j * cw + cw / 2).attr("y", top - 10).attr("text-anchor", "middle")
        .attr("data-model", k).attr("role", "button").attr("tabindex", 0)
        .attr("aria-label", `Switch to the ${D.meta.labels[k]} model pair`)
        .style("font-weight", isPair ? 700 : 400).style("cursor", "pointer").text(D.meta.short[k])
        .on("click", () => A.set({ pair: k.startsWith("lr") ? "lr" : "gbt" }))
        .on("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            A.set({ pair: k.startsWith("lr") ? "lr" : "gbt" });
            d3.select(`#vis5-body [data-model="${k}"]`).node()?.focus();
          }
        })
        .on("mousemove", e => A.showTip(e, D.meta.labels[k] + "<br><i>click to use this model</i>"))
        .on("mouseleave", A.hideTip);
    });
    rowsInfo.forEach((r, i) => {
      const low = r.fam < D.meta.min_families;
      const t = svg.append("text").attr("x", lw - 6).attr("y", top + i * rh + rh / 2 + 4).attr("text-anchor", "end")
        .style("cursor", "pointer").style("font-weight", st.slice === r.id ? 700 : 400).style("fill", low ? "#9a9a9a" : null)
        .style("font-style", r.id === SEL ? "italic" : null)
        .text((A.frozenIds.includes(r.id) ? `⚑${A.frozenIds.indexOf(r.id) + 1} ` : "") + truncate(r.id === SEL ? "Your selection" : label(r.id), Math.floor(lw / 6.4)))
        .on("click", () => { if (r.id !== SEL) A.set({ slice: st.slice === r.id ? null : r.id }); });
      t.append("title").text(label(r.id) + ` (${r.fam} families here)`);
      if (st.slice === r.id) svg.append("rect").attr("x", 0).attr("y", top + i * rh).attr("width", W).attr("height", rh)
        .attr("fill", "#fff3c4").lower();
    });
    svg.selectAll("rect.cell").data(cells).join("rect").attr("class", "cell")
      .attr("x", d => lw + models.indexOf(d.model) * cw + 1).attr("y", d => top + ids.indexOf(d.id) * rh + 1)
      .attr("width", cw - 2).attr("height", rh - 2).attr("rx", 3)
      .attr("fill", d => (d.fam < D.meta.min_families || Number.isNaN(d.v)) ? "#d0d0d0" : col(d.v))
      .style("cursor", "pointer")
      .on("click", (e, d) => A.set({ slice: d.id === SEL ? st.slice : d.id, pair: d.model.startsWith("lr") ? "lr" : "gbt" }))
      .on("mousemove", (e, d) => A.showTip(e, `<b>${label(d.id)}</b><br>${D.meta.labels[d.model]}<br>` +
        `${metric === "gap" ? "gap" : metric === "rel" ? "group gap − full population gap" : "ECE"} ${div ? A.fmtSigned(d.v) : A.fmt(d.v)}<br>` +
        `${d.n} cases, ${d.fam} families, real allowance ${A.fmt(d.prev * 100, 0)}%` +
        (d.fam < D.meta.min_families ? "<br><i>fewer than 100 families: gray, too few to trust</i>" : "")))
      .on("mouseleave", A.hideTip);
    svg.selectAll("text.cv").data(cells).join("text").attr("class", "cv")
      .attr("x", d => lw + models.indexOf(d.model) * cw + cw / 2).attr("y", d => top + ids.indexOf(d.id) * rh + rh / 2 + 4)
      .attr("text-anchor", "middle").style("pointer-events", "none")
      .style("fill", d => (Math.abs(d.v) > lim * 0.6 && d.fam >= D.meta.min_families) ? "#fff" : "#1d1d1b")
      .text(d => Number.isNaN(d.v) ? "–" : (div ? A.fmtSigned(d.v, 2) : A.fmt(d.v, 2)));
    const lg = svg.append("g").attr("transform", `translate(${lw},${top + ids.length * rh + 14})`);
    const steps = d3.range(0, 1.0001, 0.1).map(t => (div ? -lim + 2 * lim * t : lim * t));
    const stepWidth = Math.min(18, (W - lw - 81) / steps.length);
    const legendWidth = steps.length * stepWidth;
    steps.forEach((v, i) => lg.append("rect").attr("x", i * stepWidth).attr("width", stepWidth).attr("height", 10).attr("fill", col(v)));
    lg.append("text").attr("x", 0).attr("y", 24).text(div ? A.fmtSigned(-lim, 2) + (metric === "rel" ? " lower" : " too low") : "0");
    lg.append("text").attr("x", legendWidth).attr("y", 24).attr("text-anchor", "end")
      .text(div ? (metric === "rel" ? "higher " : "too high ") + A.fmtSigned(lim, 2) : A.fmt(lim, 2));
    lg.append("rect").attr("x", legendWidth + 9).attr("width", 10).attr("height", 10).attr("fill", "#d0d0d0");
    lg.append("text").attr("x", legendWidth + 23).attr("y", 9).text(`< ${D.meta.min_families} fam.`);
    const okRows = rowsInfo.filter(r => r.fam >= D.meta.min_families);
    const ans = body.append("p").attr("class", "answer");
    if (!okRows.length) { ans.html("<b>Answer:</b> no row has 100 families or more here, so no conclusion."); return; }
    const parts = okRows.map(r => {
      const cs = cells.filter(c => c.id === r.id && !Number.isNaN(c.v));
      const same = cs.every(c => c.v > 0) || cs.every(c => c.v < 0);
      const worst = d3.greatest(cs, c => Math.abs(c.v));
      return { r, same, worst };
    });
    const agree = parts.filter(p => p.same).length;
    const big = d3.greatest(parts, p => Math.abs(p.worst.v));
    ans.html(`<b>Answer:</b> ` + (metric === "ece"
      ? `biggest ECE: ${D.meta.labels[big.worst.model]} in “${label(big.r.id)}” (${A.fmt(big.worst.v)}).`
      : `all four models have gaps with the same sign in <b>${agree} of ${parts.length}</b> rows with at least ${D.meta.min_families} families. ` +
        `Largest absolute ${metric === "rel" ? "relative gap" : "gap"}: ${D.meta.short[big.worst.model]} in ` +
        `${A.frozenIds.includes(big.r.id) ? "⚑" + (A.frozenIds.indexOf(big.r.id) + 1) : "“" + label(big.r.id) + "”"} (${A.fmtSigned(big.worst.v)}).`));
  }
  function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  VApp.views.vis5 = { init, update };
})();
