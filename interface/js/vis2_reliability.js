/* global d3, VApp, VC */
(function () {
  const A = VApp;
  const W = 440, H = 360, HH = 96, M = { l: 57, r: 15, t: 10, b: 30 };
  let svg, gMain, gHist, x, y, yh, brush, nBins, showLearned = true, brushModel = "off", silent = false;

  function init() {
    const root = d3.select("#vis2-body");
    nBins = A.D.meta.n_bins;
    svg = root.append("svg").attr("viewBox", `0 0 ${W} ${H + HH + 26}`).attr("width", "100%");
    x = d3.scaleLinear([0, 1], [M.l, W - M.r]);
    y = d3.scaleLinear([0, 1], [H - M.b, M.t]);
    yh = d3.scaleLinear([0, 1], [H + HH + 16, H + 26]);
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${H - M.b})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format(".0%")));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${M.l},0)`)
      .call(d3.axisLeft(y).ticks(5).tickFormat(d3.format(".0%")));
    svg.append("text").attr("x", (M.l + W - M.r) / 2).attr("y", H - 2).attr("text-anchor", "middle")
      .text("Predicted allowance");
    svg.append("text").attr("transform", `translate(12,${(H - M.b + M.t) / 2}) rotate(-90)`).attr("text-anchor", "middle")
      .text("Real allowance (share really allowed)");
    svg.append("line").attr("class", "diag").attr("x1", x(0)).attr("y1", y(0)).attr("x2", x(1)).attr("y2", y(1));
    svg.append("text").attr("x", x(0.97)).attr("y", y(0.03)).attr("text-anchor", "end").attr("class", "muted")
      .style("fill", "#888").text("below the diagonal = predicted too high");
    gMain = svg.append("g");
    gHist = svg.append("g");
    svg.append("text").attr("x", M.l).attr("y", H + 18).style("fill", "#888")
      .text("Cases at each predicted allowance (drag to select)");
    brush = d3.brushX().extent([[M.l, H + 24], [W - M.r, H + HH + 16]]).on("end", brushed);
    svg.append("g").attr("class", "brush").call(brush);
    svg.append("g").attr("class", "legend").attr("transform", `translate(${M.l + 8},${M.t + 4})`);
    d3.select("#vis2-bins").property("value", String(nBins)).on("change", e => { nBins = +e.target.value; update(); });
    d3.select("#vis2-learned").on("change", e => { showLearned = e.target.checked; update(); });
    d3.select("#vis2-brushmodel").on("change", e => {
      brushModel = e.target.value;
      if (A.state.brush) A.set({ brush: { ...A.state.brush, model: brushModel } });
    });
    A.views.vis2.info = d3.select("#vis2-info");
  }

  function brushed(event) {
    if (silent) return;
    if (!event.selection) { A.set({ brush: null }); return; }
    const [lo, hi] = event.selection.map(point => Math.round(100 * x.invert(point)) / 100);
    if (lo === hi) {
      clearBrush();
      A.set({ brush: null });
      return;
    }
    silent = true;
    svg.select(".brush").call(brush.move, [x(lo), x(hi)]);
    silent = false;
    A.set({ brush: { model: brushModel, lo, hi } });
  }
  function clearBrush() { silent = true; svg.select(".brush").call(brush.move, null); silent = false; }

  function learnedCurve(model) {
    const st = A.state, C = A.D.curves;
    if (!showLearned || st.cohort !== "primary" || A.anyCaseFilter()) return null;
    if (st.slice) return (((C.slices || {})[st.part] || {})[st.slice] || {})[model] || null;
    return ((C.all || {})[st.part] || {})[model] || null;
  }

  function update() {
    const st = A.state;
    const base = A.baseRows();
    const rows = A.sliceRows(base);
    const models = A.pairModels();
    gMain.selectAll("*").remove();
    gHist.selectAll("*").remove();

    if (st.slice) {
      for (const m of models) {
        const rel = VC.reliability(A.periodRows(), m, nBins);
        gMain.append("path").datum(rel).attr("fill", "none").attr("stroke", A.color(m)).attr("stroke-opacity", 0.35)
          .attr("stroke-dasharray", "3 3").attr("d", d3.line().x(d => x(d.mean_p)).y(d => y(d.observed)));
      }
    }
    for (const m of models) {
      const lc = learnedCurve(m);
      if (lc) {
        const pts = lc.x.map((v, i) => ({ x: v, y: lc.y[i], lo: lc.lo[i], hi: lc.hi[i] }));
        const lo = d3.min(rows, r => r[m]), hi = d3.max(rows, r => r[m]);
        const inRange = pts.filter(p => p.x >= lo && p.x <= hi);
        gMain.append("path").datum(inRange).attr("fill", A.color(m)).attr("fill-opacity", 0.12)
          .attr("d", d3.area().x(d => x(d.x)).y0(d => y(d.lo)).y1(d => y(d.hi)));
        gMain.append("path").datum(inRange).attr("fill", "none").attr("stroke", A.color(m)).attr("stroke-width", 1.6)
          .attr("d", d3.line().x(d => x(d.x)).y(d => y(d.y)));
      }
      const rel = VC.reliability(rows, m, nBins);
      const r = d3.scaleSqrt([0, d3.max(rel, d => d.n) || 1], [2, 8]);
      const g = gMain.append("g");
      g.selectAll("line.ci").data(rel).join("line").attr("stroke", A.color(m)).attr("stroke-width", 1.2)
        .attr("x1", d => x(d.mean_p)).attr("x2", d => x(d.mean_p)).attr("y1", d => y(d.ci_lo)).attr("y2", d => y(d.ci_hi));
      g.selectAll("circle").data(rel).join("circle").attr("cx", d => x(d.mean_p)).attr("cy", d => y(d.observed))
        .attr("r", d => r(d.n)).attr("fill", A.color(m)).attr("stroke", "#fff")
        .on("mousemove", (e, d) => A.showTip(e, `<b>${A.modelLabel(m)}</b><br>band ${Math.round(d.lo * 100)}–${Math.round(d.hi * 100)}%: ` +
          `${d.n} cases<br>average predicted allowance ${A.fmt(d.mean_p * 100, 0)}%<br>real allowance ${A.fmt(d.observed * 100, 0)}% ` +
          `(95% CI ${A.fmt(d.ci_lo * 100, 0)}–${A.fmt(d.ci_hi * 100, 0)}%)<br>gap ${A.fmtSigned((d.mean_p - d.observed) * 100, 0)} points`))
        .on("mouseleave", A.hideTip);
    }

    const bins = d3.range(1, 50).map(i => i / 50);
    let maxC = 1;
    const hists = models.map(m => {
      const h = d3.bin().domain([0, 1]).thresholds(bins).value(d => d[m])(rows);
      maxC = Math.max(maxC, d3.max(h, b => b.length));
      return [m, h];
    });
    yh.domain([0, maxC]);
    for (const [m, h] of hists) {
      const counts = h.map(bin => [bin.x0, bin.length]).concat([[1, h.at(-1).length]]);
      gHist.append("path").datum(counts).attr("fill", A.color(m)).attr("fill-opacity", 0.18).attr("stroke", A.color(m))
        .attr("stroke-dasharray", m.endsWith("_off") ? "4 2" : null)
        .attr("d", d3.area().curve(d3.curveStepAfter).x(d => x(d[0])).y0(yh(0)).y1(d => yh(d[1])));
    }
    gHist.append("g").attr("class", "axis").attr("transform", `translate(${M.l},0)`).call(d3.axisLeft(yh).ticks(2));

    const leg = svg.select(".legend").html("");
    models.forEach((m, i) => {
      const g = leg.append("g").attr("transform", `translate(0,${i * 15})`);
      g.append("circle").attr("r", 5).attr("cx", 5).attr("cy", 0).attr("fill", A.color(m));
      g.append("text").attr("x", 14).attr("y", 4).text(A.modelLabel(m));
    });
    if (!rows.length) {
      A.views.vis2.info.html('<div class="answer">No cases match the current filters.</div>');
      return;
    }
    const bsr = VC.familyBootstrap(rows, Object.fromEntries(models.flatMap(m => [[m + "_ece", s => VC.ece(s, m, nBins)]])), 200);
    const [mo, mn] = models, gOff = VC.gap(rows, mo), gOn = VC.gap(rows, mn);
    const side = g => Math.abs(g) < 0.02 ? "about right on average" : g > 0 ? `too high by ${A.fmt(g * 100, 0)} points on average` : `too low by ${A.fmt(-g * 100, 0)} points on average`;
    const ece = k => {
      const { est, lo, hi } = bsr[k + "_ece"];
      return A.fmt(est) + (Number.isFinite(lo) ? ` <span class="muted">(95% CI ${A.fmt(lo)} to ${A.fmt(hi)})</span>` : "");
    };
    const families = VC.families(rows);
    A.views.vis2.info.html(`<div class="answer"><b>Answer</b> (${rows.length} cases, ${families} families, real allowance ${A.fmt(VC.prevalence(rows) * 100, 0)}%)<br>` +
      `<b>Profile off:</b> ${side(gOff)}; ECE ${ece(mo)}, MCE ${A.fmt(VC.mce(rows, mo, nBins))}<br>` +
      `<b>Profile on:</b> ${side(gOn)}; ECE ${ece(mn)}, MCE ${A.fmt(VC.mce(rows, mn, nBins))}` +
      (families < A.D.meta.min_families ? "<br><b>Fewer than 100 families. Descriptive only.</b>" : "") + "</div>" +
      (st.brush ? '<div class="note">This chart shows the full distribution around the selected range.</div>' : "") +
      (st.slice ? '<div class="note">Faint lines show the full population of this period and cohort.</div>' : "") +
      (learnedCurve(models[0]) || !showLearned ? "" : '<div class="note">The fitted curve is unavailable for this selection.</div>'));
  }

  VApp.views.vis2 = { init, update, clearBrush, info: null };
})();
