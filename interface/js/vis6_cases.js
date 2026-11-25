/* global d3, VApp */
(function () {
  const A = VApp;
  const LIMIT = 300;
  let sortKey = "date";
  let descending = true;

  function update() {
    const st = A.state;
    const [off, on] = A.pairModels();
    const outcome = y => y === 1 ? "allowed" : "rejected";
    const columns = [
      { key: "date", label: "Reply date", sort: row => row.date },
      { key: "flag", label: "Flagged groups", sort: row => row.stars?.[0] ?? Infinity,
        text: row => (row.stars || []).map(i => "⚑" + i).join(", ") },
      { key: "off", label: A.D.meta.short[off], sort: row => row[off], text: row => A.fmt(row[off] * 100, 0) + "%" },
      { key: "on", label: A.D.meta.short[on], sort: row => row[on], text: row => A.fmt(row[on] * 100, 0) + "%" },
      { key: "outcome", label: A.D.meta.synthetic ? "Practice outcome" : "Outcome", sort: row => row.y,
        text: row => outcome(row.y) },
    ];
    const key = columns.find(column => column.key === sortKey).sort;
    const compare = descending ? d3.descending : d3.ascending;
    const rows = A.selectedRows().sort((a, b) => compare(key(a), key(b)) || d3.ascending(a.id, b.id));
    const shown = rows.slice(0, LIMIT);
    const selected = shown.find(row => row.id === st.caseId) ?? shown[0];
    st.caseId = selected?.id ?? null;

    const body = d3.select("#vis6-table");
    const active = body.node().contains(document.activeElement) ? document.activeElement.dataset : {};
    const scroll = body.node().scrollTop;
    body.html("");
    body.append("div").attr("class", "note").text(
      `${rows.length} cases${rows.length > LIMIT ? ` · showing first ${LIMIT}` : ""}`);
    if (!rows.length) {
      detail(null);
      return;
    }

    const table = body.append("table").attr("class", "grid").attr("aria-label", "Selected cases");
    const headings = table.append("thead").append("tr").selectAll("th").data(columns).join("th")
      .attr("scope", "col").attr("aria-sort", c => c.key === sortKey ? (descending ? "descending" : "ascending") : null)
      .append("button").attr("type", "button").attr("class", "sort-button").attr("data-sort", c => c.key)
      .text(c => c.label + (sortKey === c.key ? (descending ? " ▼" : " ▲") : ""))
      .on("click", (event, c) => {
        descending = c.key === sortKey ? !descending : true;
        sortKey = c.key;
        body.node().scrollTop = 0;
        update();
      });
    const tr = table.append("tbody").selectAll("tr").data(shown).join("tr")
      .attr("class", d => d.id === st.caseId ? "row selected" : "row")
      .on("click", (event, row) => { st.caseId = row.id; update(); });
    const buttons = tr.append("td").append("button").attr("type", "button").attr("class", "case-button")
      .attr("data-case", row => row.id).attr("aria-pressed", row => String(row.id === st.caseId))
      .attr("aria-label", row => `Application ${row.app}, reply on ${row.date}`)
      .text(row => row.date);
    for (const c of columns.slice(1)) {
      const cls = { flag: "star", off: "num", on: "num" }[c.key];
      tr.append("td").attr("class", cls || null).text(c.text);
    }
    body.node().scrollTop = scroll;
    if (active.sort) headings.filter(c => c.key === active.sort).node()?.focus({ preventScroll: true });
    if (active.case) buttons.filter(c => c.id === active.case).node()?.focus({ preventScroll: true });
    detail(selected);
  }

  function detail(c) {
    const box = d3.select("#vis6-detail").html("");
    if (!c) {
      box.append("p").attr("class", "muted").text("No cases match the current selection.");
      return;
    }

    const D = A.D;
    const docs = c.docs ?? {};
    box.append("h3").text(`Application ${c.app} · reply on ${c.date}`);
    const fields = box.append("dl").attr("class", "kv");
    function add(label, value, source) {
      fields.append("dt").attr("class", "muted").text(label);
      const cell = fields.append("dd").text(value);
      if (source) cell.append("div").attr("class", "muted").text(source);
    }

    add("Predicted allowance", D.meta.models.map(m => `${D.meta.short[m]} ${A.fmt(c[m] * 100, 0)}%`).join(" · "));
    add(D.meta.synthetic ? "Practice outcome" : "Real outcome", c.y ? "allowed" : "rejected");
    add("Examiner ID", c.examiner);
    if (A.examinerGroupEnabled()) {
      const group = (D.meta.ex_groups || {})[c.ex_group] || "G" + c.ex_group;
      add("Examiner group", group, `${c.ex_n_before} decisions mailed before ${D.meta.ex_group_cutoff || "2015-01-01"}`);
    }
    add("Flagged groups", (c.stars || []).map(k => `⚑${k} ${A.ruleLabel(A.frozenIds[k - 1])}`).join(" · ") || "None");
    add("Art unit / tech center", `${c.art_unit} / ${c.tc}`);
    add("Round", `${c.round_n}${c.rce ? " (RCE)" : ""}`);
    const grounds = ["101", "102", "103", "112"].filter(g => c["g" + g]).map(g => "§" + g);
    if (c.g_dp) grounds.push("double patenting");
    add("Grounds in letter", grounds.join(", ") || (docs.ground_letter ? "None found" : "Source text unavailable"), docs.ground_letter);
    add("Filing year", c.filing_year ?? "–");
    add("Letter answered", `${D.meta.prior_types[c.prior_type] || c.prior_type} · ${c.prior_date}`, docs.prior);
    add("Applicant reply", c.date, docs.reply);
    add(D.meta.synthetic ? "Next letter in the original record" : "Next letter", c.outcome_date, docs.next);
    add("Family", c.family);
    if (D.meta.synthetic) {
      box.append("p").attr("class", "note").text("Practice predictions and outcomes are simulated. Document references come from the original case records.");
      return;
    }
    add("Profile-on history", c.primary
      ? `${c.prof_s} allowance${c.prof_s === 1 ? "" : "s"} in ${c.prof_n} earlier decisions · smoothed rate ${A.fmt(c.prof_rate * 100, 0)}%`
      : `Unconfirmed examiner · art-unit rate ${A.fmt(c.au_rate * 100, 0)}% used as fallback`);

    if (!c.primary) {
      box.append("p").attr("class", "note").text("No examiner-specific outcomes were used for this checkpoint.");
      return;
    }
    const sources = D.sources?.sources?.[c.id] ?? [];
    if (!sources.length) {
      box.append("p").attr("class", "note").text(c.prof_n
        ? "The export contains no dated sources for this checkpoint."
        : "No earlier examiner decisions were available. The rate falls back to the art-unit rate.");
      return;
    }

    box.append("h3").text(`Earlier decisions · showing ${sources.length} of ${c.prof_n}`);
    const dated = d => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d);
    const valid = dated(c.date) && sources.every(s => dated(s[2]));
    const late = valid ? sources.filter(s => s[2] >= c.date).length : 0;
    if (!valid || late) {
      box.append("p").attr("class", "bad").text(valid
        ? `${late} displayed decision date(s) fall on or after the reply date.`
        : "Some displayed decision dates could not be verified.");
    } else {
      box.append("p").attr("class", "ok").text(`All displayed decision dates precede ${c.date}.`);
    }
    const table = box.append("table").attr("class", "grid").attr("aria-label", "Dated examiner history");
    table.append("thead").append("tr").selectAll("th")
      .data(["Decision date", "Application", "Decision", "Document"]).join("th").attr("scope", "col").text(d => d);
    const tr = table.append("tbody").selectAll("tr").data(sources).join("tr");
    tr.append("td").text(s => s[2]);
    tr.append("td").text(s => s[0]);
    tr.append("td").text(s => s[3] ? "allowed" : "rejected");
    tr.append("td").attr("class", "muted").text(s => s[4] || "–");
  }

  VApp.views.vis6 = { init() {}, update };
})();
