/* global d3, VC */
window.VApp = (function () {
  const D = window.VML;
  const views = {};
  if (!D) {
    return { views, start: () => {
      const file = document.querySelector('script[src^="data/"]').getAttribute("src");
      d3.selectAll("#filter-panel, #view-nav, #app, #edit-filters, button.help").property("hidden", true);
      d3.select("#selection").text(`Missing ${file}. Run bash run_all.sh from the project root, then reload.`);
    } };
  }

  D.meta.parts = {
    dev_search: "2014 part A · discovery",
    dev_assess: "2014 part B · re-check",
    dev: "2014 (A + B)",
    test: "2015–2017 · final test",
  };
  const FILTERS = [
    { key: "ex_group", label: "Examiner group" },
    { key: "examiner", label: "Examiner ID" },
    { key: "tc", label: "Tech center" },
    { key: "art_unit", label: "Art unit" },
    { key: "prior_type", label: "Letter answered" },
    { key: "round_c", label: "Round" },
    { key: "rce", label: "RCE filed", advanced: true },
    { key: "g101", label: "§101 rejection", advanced: true },
    { key: "g102", label: "§102 rejection", advanced: true },
    { key: "g103", label: "§103 rejection", advanced: true },
    { key: "g112", label: "§112 rejection", advanced: true },
    { key: "g_dp", label: "Double patenting rejection", advanced: true },
    { key: "filing_year", label: "Filing year", advanced: true },
    { key: "hist_tier", label: "Examiner history", advanced: true },
  ];
  function noFilters() { return Object.fromEntries(FILTERS.map(f => [f.key, "all"])); }
  const state = {
    part: D.meta.synthetic ? "dev_search" : "test", cohort: "primary", pair: "lr", cvd: "",
    filters: noFilters(), slice: null, brush: null, caseId: null,
  };
  const controls = { part: "#f-part", cohort: "#f-cohort", pair: "#f-pair", cvd: "#f-cvd" };
  const byRule = new Map(D.slices.candidates.map(group => [group.rule_id, group]));
  const frozenIds = D.slices.frozen.rule_ids || [];

  function pairModels() { return state.pair === "lr" ? ["lr_off", "lr_on"] : ["gbt_off", "gbt_on"]; }
  function modelLabel(m) { return D.meta.labels[m]; }
  function color(m) { return D.meta.colors[m]; }
  function rulePreds(id) {
    const r = byRule.get(id) || (D.slices.frozen.slices || []).find(s => s.rule_id === id);
    if (!r) return [];
    return typeof r.preds === "string" ? JSON.parse(r.preds) : r.preds;
  }
  function ruleLabel(id) { const r = byRule.get(id); return r ? r.label : id; }

  function examinerGroupEnabled() { return state.part === "test"; }

  function periodRows(st = state) {
    return D.cases.filter(c =>
      (st.part === "dev" ? c.block === "dev" : st.part === "test" ? c.block === "test" : c.part === st.part) &&
      (st.cohort === "all" || c.primary === 1));
  }
  function passes(c, filters) {
    for (const k in filters) {
      const v = filters[k];
      if (v !== "all" && String(c[k]) !== v) return false;
    }
    return true;
  }
  function baseRows() { const f = state.filters; return periodRows().filter(c => passes(c, f)); }
  function activeFilters() { return FILTERS.filter(f => state.filters[f.key] !== "all"); }
  function anyCaseFilter() { return activeFilters().length > 0; }
  function filterText(key, value) {
    if (value === "all") return "all";
    if (key === "ex_group") return (D.meta.ex_groups || {})[value] || "G" + value;
    if (key === "prior_type") return (D.meta.prior_types || {})[value] || value;
    if (key === "round_c") return value === "3" ? "3+" : value;
    if (key === "hist_tier") return (D.meta.tiers[+value] || value) + " earlier decisions";
    if (["g101", "g102", "g103", "g112", "g_dp", "rce"].includes(key)) return value === "1" ? "yes" : "no";
    return value;
  }
  function sliceRows(rows) {
    if (!state.slice) return rows;
    const p = rulePreds(state.slice);
    return rows.filter(c => VC.matches(c, p));
  }
  function brushRows(rows) {
    if (!state.brush) return rows;
    const [off, on] = pairModels(); const k = state.brush.model === "on" ? on : off;
    return rows.filter(c => c[k] >= state.brush.lo && c[k] <= state.brush.hi);
  }
  function selectedRows() { return brushRows(sliceRows(baseRows())); }

  function set(patch) {
    Object.assign(state, patch);
    if (!examinerGroupEnabled() && state.filters.ex_group !== "all") {
      state.filters = { ...state.filters, ex_group: "all" };
    }
    hideTip();
    render();
  }

  function render() {
    for (const [key, selector] of Object.entries(controls)) {
      d3.select(selector).property("value", state[key]);
    }
    d3.select("#app").style("filter", state.cvd ? `url(#cvd-${state.cvd})` : null);
    renderCaseFilters();
    renderSelection();
    for (const k of Object.keys(views)) {
      try { views[k].update(state); } catch (e) { console.error(k, e); }
    }
  }

  function renderSelection() {
    const sel = d3.select("#selection").html("");
    const rows = selectedRows();
    const summary = sel.append("div").attr("class", "selection-summary");
    summary.append("strong").text(`${rows.length.toLocaleString("en-US")} cases`);
    summary.append("span").text(`· ${VC.families(rows).toLocaleString("en-US")} families`);
    summary.append("span").attr("class", "selection-context")
      .text(`${D.meta.parts[state.part]} · ${state.cohort === "primary" ? "Confirmed examiners" : "All cases"}`);
    const filters = activeFilters();
    if (!filters.length && !state.slice && !state.brush) return;
    const chips = sel.append("div").attr("class", "selection-chips");
    function addChip(label, removeLabel, clear) {
      const chip = chips.append("span").attr("class", "chip");
      chip.append("span").text(label);
      chip.append("button").attr("class", "x").attr("type", "button").attr("aria-label", removeLabel).text("×")
        .on("click", () => {
          clear();
          const next = document.querySelector(".selection-chips .x, #edit-filters");
          next?.focus({ preventScroll: true });
        });
    }
    for (const f of filters) {
      addChip(`${f.label}: ${filterText(f.key, state.filters[f.key])}`, `Remove ${f.label} filter`,
        () => set({ filters: { ...state.filters, [f.key]: "all" } }));
    }
    if (state.slice) {
      addChip("Flagged group: " + ruleLabel(state.slice), "Remove flagged group filter", () => set({ slice: null }));
    }
    if (state.brush) {
      const [off, on] = pairModels();
      const label = `${modelLabel(state.brush.model === "on" ? on : off)}: predicted allowance ` +
        `${Math.round(state.brush.lo * 100)}–${Math.round(state.brush.hi * 100)}%`;
      addChip(label, "Remove predicted allowance range", () => {
        views.vis2.clearBrush();
        set({ brush: null });
      });
    }
    chips.append("button").attr("type", "button").attr("class", "clear-filters").text("Clear all").on("click", () => {
      views.vis2.clearBrush();
      set({ slice: null, brush: null, filters: noFilters() });
      document.getElementById("edit-filters").focus({ preventScroll: true });
    });
  }

  const tip = d3.select("#tooltip");
  function showTip(event, html) {
    tip.html(html).style("display", "block");
    place(tip, event.clientX + 14, event.clientY + 12);
  }
  function hideTip() { tip.style("display", "none"); }

  function place(box, x, y) {
    const { offsetWidth, offsetHeight } = box.node();
    box.style("left", Math.max(8, Math.min(x, window.innerWidth - offsetWidth - 8)) + "px")
      .style("top", Math.max(8, Math.min(y, window.innerHeight - offsetHeight - 8)) + "px");
  }

  const HELP = {
    words: "<b>Words used on this page</b><br>" +
      "<b>Case</b> = one moment in a patent application: the applicant has just replied to the examiner's letter. We predict " +
      "the examiner's <i>next</i> letter: <b>allowed</b> (notice of allowance) or <b>rejected</b> (another office action).<br>" +
      "<b>Predicted allowance</b> = the model's probability (0–100%) that the next letter is an allowance.<br>" +
      "<b>Real allowance</b> = the share of cases that really were allowed.<br>" +
      "<b>Gap</b> = predicted allowance − real allowance, for a group of cases. + = the model said too high, − = too low, 0 = right.<br>" +
      "<b>Group</b> = the cases that match some conditions (for example a flagged group). <b>Full population</b> = all cases " +
      "of the same period, the group included. Predicted allowance, real allowance and gap are computed the same way for both.<br>" +
      "<b>ECE</b> (expected calibration error) = put the cases in 10 bins by predicted allowance (0–10%, 10–20%, …); " +
      "in each bin take the size of the gap; average the bins, weighted by how many cases each has. 0 is perfect. " +
      "<b>MCE</b> = the biggest of those bin gaps.<br>" +
      "<b>AUROC</b> = area under the ROC curve. It measures how often an allowed case outranks a rejected case, " +
      "with ties counting half. Higher is better.<br>" +
      "<b>Brier score</b> = average of (predicted allowance − outcome)², outcome 1 = allowed, 0 = rejected. Lower is better. " +
      "<b>Log loss</b> = the same idea with a log penalty. Both charge for being off and for not separating cases (" +
      "a model can have ECE 0 and still be useless, so we always show AUROC and Brier next to ECE).<br>" +
      "<b>LR</b> = logistic regression, <b>Trees</b> = boosted trees (the two kinds of model).<br>" +
      "<b>Profile off / on</b> = the same model without / with the examiner's profile (his examiner ID + how many of his earlier " +
      "decisions were known and how many were allowances, all dated before the case).<br>" +
      "<b>Examiner history</b> = how many of his earlier decisions were known at that time (0–5, 6–13, 14+).<br>" +
      "<b>Family</b> = applications that come from the same first application. They are not independent, so we count " +
      "families, and we need at least 100 families before we trust a group's numbers (fewer = gray).<br>" +
      "<b>95% CI</b> = 95% confidence interval. Wilson bars in Visualizations 1 and 2 use checkpoint counts. " +
      "Family bootstrap intervals keep all cases from each resampled family together.<br>" +
      "<b>Flagged group (⚑)</b> = one of five groups the computer flagged in 2014 because its gap was far from the gap of the full population " +
      "(all cases of that period, the group included). The flag means “look here”, not “good”, and not “a proven problem”: " +
      "with one calibrated simulated score, Experiment 3 found at least one passing group in 24 of 50 runs.<br>" +
      "<b>Periods</b>: 2008–2013 trains the models; 2014 part A is where the computer flags groups; 2014 part B re-checks " +
      "them; 2015–2017 is the final test that nothing was tuned on.",
    filters: "<b>Your case.</b> Pick what you know about your own application: your examiner, art unit, the letter you are " +
      "answering, the round, whether you filed an RCE (request for continued examination), the rejection grounds in that " +
      "letter, the filing year. Open <b>More filters</b> for rejection grounds and other case details. Leave a box on <i>all</i> if you " +
      "do not know it. Each option shows how many cases it has. Remove a filter with × in the selection bar.<br>" +
      "Grounds: §101 = not the kind of thing that can be patented; §102 = not new; §103 = obvious; §112 = description " +
      "unclear or not supported; double patenting = overlaps the applicant's own earlier patent.<br>" +
      "<b>Examiner group:</b> G1 through G5 are ordered by the examiner's allowance rate before 2015. G0 has fewer " +
      "than five earlier decisions. These groups are used for filtering 2015–2017 cases. The filter is disabled for " +
      "2014 because the group labels include outcomes from that year. Examiner IDs are hashed codes.",
    vis1: "<b>Question:</b> for cases like mine, how close was the predicted allowance to the real allowance?<br>" +
      "<b>How to read it:</b> if you pick an examiner, the card shows his full record in our data and his group. Each row is a " +
      "set of past cases, from narrow (exactly your filters) to wide (the full population of this period). Colored dots = average " +
      "predicted allowance (light = profile off, dark = profile on). Black diamond = real allowance with its 95% CI. The distance " +
      "between a dot and the diamond is the gap. Rows with fewer than " + (D.meta.view_min_cases || 30) + " cases are gray: " +
      "read the next row down. Click a row to use its filters. With nothing chosen in “Your case”, the rows are the full " +
      "population and each tech center: click one to start.<br><b>Answer:</b> the box under the chart.",
    vis2: "<b>Question:</b> over the whole range of predicted allowance, is it close to the real allowance? (The " +
      "reliability diagram is the standard chart for this.)<br><b>How to read it:</b> across = predicted allowance; up = real " +
      "rate. The cases are put in bins by predicted allowance (10 bins = 0–10%, 10–20%, …); each dot is one bin (bigger dot = " +
      "more cases; vertical line = 95% CI). On the dashed diagonal the predicted allowance equals the real allowance. Below the " +
      "diagonal = predicted too high; above = too low. The fitted line is the learned curve from Calibrate, which " +
      "does not depend on the bins. Change the number of bins to check the picture does not depend on them. " +
      "Always read the bars underneath: how many cases got each predicted allowance. Drag on the bars to keep only cases in " +
      "that range; the selected cases update across the dashboard.<br><b>Answer:</b> the box next to the chart (gap, ECE and MCE).",
    vis3: "<b>Question:</b> does the profile rank cases better and bring the predicted allowance closer to the real allowance? " +
      "Is that different by examiner history, round, or tech center?<br><b>Top, ROC curve:</b> move a threshold from " +
      "100% down to 0%; at each threshold, the true positive rate (share of allowed cases above it, up) against the false " +
      "positive rate (share of rejected cases above it, across). A curve closer to the top-left ranks cases better; the dashed " +
      "diagonal represents chance ranking. AUROC = the area under the curve.<br>" +
      "<b>Measures by group:</b> for the selected cases and for each group, the chosen measure for profile off (light) and on (dark) on " +
      "exactly the same cases, with 95% CIs (200 family re-draws), and on − off at the far right. “better” / “worse” only when " +
      "the group has at least 100 families and the entire difference interval is on one side of zero. The 0–5 tier " +
      "includes several history sizes, and the profile-on model can also use a known examiner ID.<br>" +
      "<b>Answer:</b> the full 2015–2017 selection shows Experiment 2 results. Filtered selections use live intervals.",
    vis4: "<b>Question:</b> where was the gap between predicted allowance and real allowance biggest, and does it stay later?<br>" +
      "<b>How the computer flags groups</b> (Slice Finder), using only 2014 part A: (1) try every group described by " +
      "one condition (e.g. “round 1”) or two conditions (e.g. “round 1 and no §103 rejection”); (2) keep groups with at least " +
      "100 families in both halves of 2014; (3) keep groups whose gap differs from the full population's gap by at least 5 points, with a " +
      "95% CI that does not include 0 (two tests, size and certainty, because “hunting for bad subgroups " +
      "guarantees you find some”); (4) sort by the biggest ECE over the four models; the first five = ⚑1–⚑5. The same data " +
      "always gives the same five. The flag means “look here”, not “good”.<br><b>Table:</b> each condition sits in a fixed " +
      "column (Technology, Examiner, Stage, Ground), which makes rule lists easier to read (Yuan, Nov & Bertini). " +
      "The last column compares each filtered group with the full population of the same period and cohort. Row tooltips " +
      "give the current family count. Click a rule to add it as a filter.<br>" +
      "<b>Lower part (extension question):</b> one small chart per flagged group, gap per period, 2014 part A shaded as the " +
      "period where it was found. The gray line in each " +
      "chart is the full population gap: compare the group with the gray line, not with 0, because the full population gap " +
      "also moves. “Threshold met” = in 2015–2017 the group gap is at least 5 points away from the full population " +
      "gap, at least 100 families, and a 95% CI that excludes zero. Re-check labels refer to profile off. These charts " +
      "use all cases of the chosen cohort.<br>" +
      "<b>How to read the result:</b> a flag is a lead to check, not a finding. Check three things: does the group pass again in " +
      "2014 part B (same year, other families)? Do the five groups overlap (then they are one pattern, not five)? Is the group's " +
      "own gap still large in 2015–2017, or only its distance to a full population whose gap moved?<br>" +
      "<b>Answer:</b> the box at the bottom.",
    vis5: "<b>Question:</b> do all four models have the same gap in these groups?<br>" +
      "<b>How to read it:</b> rows = your current selection, then the flagged " +
      "groups; columns = the four models. Default measure: <b>group gap − full population gap</b> (the same comparison used to flag the " +
      "groups): each model has its own overall gap (for example LR, profile off is too high for the full population), so this removes it " +
      "and shows what is special about the group. Red = group gap higher than the full population gap, blue = lower, white = same, same scale both " +
      "ways (diverging scale). You can also show the plain gap or ECE. Gray = fewer than 100 families. Click a row to add that group as " +
      "a filter; click a column name to switch the model.<br><b>Answer:</b> the box under the chart.",
    vis6: "<b>Question:</b> which real cases are behind the numbers, and which earlier decisions built the profile? (Calibrate's " +
      "instance view; “what was known when”.)<br><b>How to read it:</b> the selected cases, one per row. " +
      "Click one to see its USPTO document codes, grounds, predictions, and the dated history shown for its profile. " +
      "The date check applies to the displayed source outcomes.",
  };
  function initHelp() {
    const box = d3.select("#helpbox");
    let active;
    function close(restoreFocus = false) {
      if (!active) return;
      box.style("display", "none");
      d3.select(active).attr("aria-expanded", "false");
      if (restoreFocus) active.focus();
      active = null;
    }
    d3.selectAll("button.help").on("click", function (event) {
      event.stopPropagation();
      const previous = active;
      close();
      if (previous === this) return;
      active = this;
      d3.select(this).attr("aria-expanded", "true");
      box.html(HELP[this.dataset.help]).style("display", "block");
      const anchor = this.getBoundingClientRect();
      const dismiss = box.append("div").append("button").attr("type", "button").text("Close")
        .on("click", () => close(true));
      place(box, anchor.left, anchor.bottom + 8);
      dismiss.node().focus();
    });
    box.on("click", event => event.stopPropagation());
    d3.select("body").on("click.help", () => close())
      .on("keydown.help", event => { if (event.key === "Escape") close(true); });
  }

  // Facet counts apply all of the other case filters.
  function filterOptions(key) {
    const others = { ...state.filters, [key]: "all" };
    const rows = periodRows().filter(c => passes(c, others));
    const counts = d3.rollup(rows, v => v.length, c => String(c[key]));
    const keys = Array.from(counts.keys()).filter(k => k !== "null" && k !== "undefined");
    const num = ["round_c", "hist_tier", "ex_group", "filing_year", "rce", "g101", "g102", "g103", "g112", "g_dp"];
    keys.sort(num.includes(key) ? (a, b) => (+a) - (+b) : d3.ascending);
    if (key === "examiner") {
      const au = d3.rollup(rows, v => d3.greatest(d3.rollups(v, w => w.length, c => c.art_unit), x => x[1])[0], c => c.examiner);
      return keys.map(k => [k, `${k} · art unit ${au.get(k)} · ${counts.get(k)} cases`]);
    }
    return keys.map(k => [k, `${filterText(key, k)} (${counts.get(k)})`]);
  }
  function renderCaseFilters() {
    const main = d3.select("#casefilters");
    const extra = d3.select("#casefilters-more");
    for (const f of FILTERS) {
      const box = f.advanced ? extra : main;
      let sel = box.select(`#ff-${f.key}`);
      if (sel.empty()) {
        const lab = box.append("label");
        lab.append("span").text(f.label);
        sel = lab.append("select").attr("id", `ff-${f.key}`)
          .on("change", e => set({ filters: { ...state.filters, [f.key]: e.target.value } }));
      }
      const disabled = f.key === "ex_group" && !examinerGroupEnabled();
      const opts = disabled ? [["all", "2015–2017 only"]] : [["all", "all"], ...filterOptions(f.key)];
      const cur = state.filters[f.key];
      if (cur !== "all" && !opts.some(o => o[0] === cur)) opts.push([cur, filterText(f.key, cur) + " (0)"]);
      sel.selectAll("option").data(opts, d => d[0]).join("option").attr("value", d => d[0]).text(d => d[1]);
      sel.property("value", cur).property("disabled", disabled)
        .attr("aria-describedby", disabled ? "examiner-group-note" : null);
    }
    d3.select("#examiner-group-note").property("hidden", examinerGroupEnabled());
    const count = activeFilters().filter(f => f.advanced).length;
    d3.select("#extra-filter-count").text(`${count} active`).property("hidden", count === 0);
  }

  function initFilters() {
    const part = d3.select("#f-part");
    for (const [k, v] of Object.entries(D.meta.parts)) {
      part.append("option").attr("value", k).attr("title", v).text(v.split(" · ")[0]);
    }
    for (const [key, selector] of Object.entries(controls)) {
      d3.select(selector).on("change", event => set({ [key]: event.target.value }));
    }
  }

  function fmt(v, d = 3) { return Number.isFinite(v) ? v.toFixed(d) : "–"; }
  function fmtSigned(v, d = 3) {
    if (!Number.isFinite(v)) return "–";
    const rounded = Number(v.toFixed(d));
    return (rounded > 0 ? "+" : "") + rounded.toFixed(d);
  }

  const FILES = [
    ["Cases and predicted allowances (Visualizations 1, 6)", ["models/predictions.csv"], "built from features/features.csv"],
    ["Examiner history and examiner groups (filters, examiner card)", ["profiles/profile_sources.json", "profiles/examiner_groups.json", "profiles/tiers.json"]],
    ["Full population measures and learned curves (Visualizations 2–3)", ["metrics/metrics_overall.csv", "metrics/learned_curves.json"]],
    ["Flagged groups ⚑1–⚑5 (Visualizations 4–5)", ["slices/candidates.csv", "slices/frozen_top5.json", "slices/frozen_assessment.csv",
      "slices/slice_curves.json"]],
    ["Experiment 2 (profile off vs on, same 2015–2017 cases; Visualization 3 Answer)", ["e2/e2_paired.csv"]],
  ];
  function renderFooter() {
    const f = D.meta.files || {};
    const practice = D.meta.synthetic;
    const details = d3.select("#footer").append("details").attr("class", "sources");
    const summary = details.append("summary");
    summary.append("span").text("Data sources");
    const content = details.append("div").attr("class", "sources-content");
    const file = content.append("p").attr("class", "source-export");
    file.append("strong").text("Dashboard export");
    file.append("code").text(f.page || `interface/data/vml_data${practice ? "_synthetic" : ""}.js`);
    if (practice) content.append("p").text(
      "The practice export uses the original cases and dated examiner records. Predictions, outcomes, and flagged groups are generated for practice.");
    const ul = content.append("ul").attr("class", "files");
    const items = practice ? FILES.slice(0, 2) : (f.items || FILES);
    for (const [what, paths, note] of items) {
      const line = ul.append("li");
      line.append("strong").text(what);
      line.append("div").attr("class", "source-paths").selectAll("code").data(paths).join("code").text(path => path);
      if (note) line.append("span").attr("class", "note").text(note);
    }
  }

  function start() {
    let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(render, 250); });
    if (D.meta.synthetic) {
      document.title = "Practice data · Can You Trust Personalized Odds?";
      d3.select("#practice-mark").property("hidden", false);
      d3.select("#practice-note").property("hidden", false);
    }
    initFilters();
    initHelp();
    for (const k of Object.keys(views)) views[k].init();
    renderFooter();
    render();
  }

  return { D, state, views, set, baseRows, periodRows, passes, anyCaseFilter, noFilters, examinerGroupEnabled,
    sliceRows, brushRows, selectedRows, pairModels, modelLabel, color,
    rulePreds, ruleLabel, frozenIds, showTip, hideTip, fmt, fmtSigned, start };
})();
