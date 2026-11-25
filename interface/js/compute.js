/* global d3 */
window.VC = (function () {
  function binIndex(p, nBins) {
    // Match numpy.linspace edges and right-sided search in vml/metrics.py.
    const step = 1 / nBins;
    const index = Math.min(nBins - 1, Math.floor(p * nBins));
    if (index > 0 && p < index * step) return index - 1;
    if (index < nBins - 1 && p >= (index + 1) * step) return index + 1;
    return index;
  }

  function ece(rows, key, nBins = 10) {
    if (!rows.length) return NaN;
    const sp = new Float64Array(nBins), sy = new Float64Array(nBins);
    for (const r of rows) { const b = binIndex(r[key], nBins); sp[b] += r[key]; sy[b] += r.y; }
    let s = 0; for (let b = 0; b < nBins; b++) s += Math.abs(sy[b] - sp[b]);
    return s / rows.length;
  }
  function gap(rows, key) { return rows.length ? d3.mean(rows, r => r[key] - r.y) : NaN; }
  function brier(rows, key) { return rows.length ? d3.mean(rows, r => (r[key] - r.y) ** 2) : NaN; }
  function auroc(rows, key) {
    const n1 = rows.reduce((a, r) => a + (r.y ? 1 : 0), 0), n0 = rows.length - n1;
    if (!n1 || !n0) return NaN;
    const s = rows.map(r => [r[key], r.y]).sort((a, b) => a[0] - b[0]);
    let rankSum = 0, i = 0;
    while (i < s.length) {                       // average ranks over ties
      let j = i; while (j + 1 < s.length && s[j + 1][0] === s[i][0]) j++;
      const avg = (i + j) / 2 + 1;
      for (let k = i; k <= j; k++) if (s[k][1]) rankSum += avg;
      i = j + 1;
    }
    return (rankSum - n1 * (n1 + 1) / 2) / (n1 * n0);
  }
  function roc(rows, key) {
    const n1 = rows.reduce((a, r) => a + (r.y ? 1 : 0), 0), n0 = rows.length - n1;
    if (!n1 || !n0) return [];
    const s = rows.map(r => [r[key], r.y]).sort((a, b) => b[0] - a[0]);
    const pts = [[0, 0]]; let tp = 0, fp = 0, i = 0;
    while (i < s.length) {
      let j = i; while (j + 1 < s.length && s[j + 1][0] === s[i][0]) j++;
      for (let k = i; k <= j; k++) { if (s[k][1]) tp++; else fp++; }
      pts.push([fp / n0, tp / n1]); i = j + 1;
    }
    return pts;
  }
  function logloss(rows, key) {
    if (!rows.length) return NaN;
    return d3.mean(rows, r => { const p = Math.min(1 - 1e-6, Math.max(1e-6, r[key])); return -(r.y * Math.log(p) + (1 - r.y) * Math.log(1 - p)); });
  }
  function mce(rows, key, nBins = 10) {
    if (!rows.length) return NaN;
    const sp = new Float64Array(nBins), sy = new Float64Array(nBins), n = new Float64Array(nBins);
    for (const r of rows) { const b = binIndex(r[key], nBins); sp[b] += r[key]; sy[b] += r.y; n[b]++; }
    let m = 0; for (let b = 0; b < nBins; b++) if (n[b]) m = Math.max(m, Math.abs(sy[b] - sp[b]) / n[b]);
    return m;
  }
  function prevalence(rows) { return rows.length ? d3.mean(rows, r => r.y) : NaN; }
  function families(rows) { return new Set(rows.map(r => r.fam)).size; }

  function wilson(k, n, z = 1.96) {
    if (!n) return [NaN, NaN];
    const ph = k / n, den = 1 + z * z / n, c = (ph + z * z / (2 * n)) / den;
    const h = z * Math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den;
    return [Math.max(0, c - h), Math.min(1, c + h)];
  }

  function reliability(rows, key, nBins = 10) {
    const out = [];
    for (let b = 0; b < nBins; b++) out.push({ bin: b, lo: b / nBins, hi: (b + 1) / nBins, n: 0, sp: 0, sy: 0 });
    for (const r of rows) { const o = out[binIndex(r[key], nBins)]; o.n++; o.sp += r[key]; o.sy += r.y; }
    return out.filter(o => o.n > 0).map(o => {
      const [l, h] = wilson(o.sy, o.n);
      return { ...o, mean_p: o.sp / o.n, observed: o.sy / o.n, ci_lo: l, ci_hi: h };
    });
  }

  // Mulberry32 keeps intervals stable for a given selection.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function familyBootstrap(rows, fns, B = 200, seed = 20261119) {
    const families = Array.from(d3.group(rows, row => row.fam).values());
    const random = rng(seed);
    const entries = Object.entries(fns);
    const results = Object.fromEntries(entries.map(([key, measure]) => [key, { est: measure(rows), draws: [] }]));
    // Measures share the same family resamples so on − off intervals remain paired.
    if (families.length > 1) {
      for (let b = 0; b < B; b++) {
        const sample = [];
        for (let i = 0; i < families.length; i++) sample.push(...families[Math.floor(random() * families.length)]);
        for (const [key, measure] of entries) results[key].draws.push(measure(sample));
      }
    }
    for (const result of Object.values(results)) Object.assign(result, interval(result.draws));
    return results;
  }

  function interval(draws) {
    const sorted = draws.filter(Number.isFinite).sort(d3.ascending);
    return { lo: d3.quantileSorted(sorted, 0.025), hi: d3.quantileSorted(sorted, 0.975) };
  }

  function matches(c, preds) {
    for (const p of preds) {
      const v = c[p.attr];
      if (p.op === "==") { if (String(v) !== String(p.value)) return false; }
      else if (p.op === "!=") { if (String(v) === String(p.value)) return false; }
      else if (p.op === ">=") { if (!(+v >= +p.value)) return false; }
      else if (p.op === "<=") { if (!(+v <= +p.value)) return false; }
    }
    return true;
  }

  return { ece, mce, gap, brier, logloss, auroc, roc, prevalence, families, wilson, reliability, familyBootstrap, interval, matches };
})();
