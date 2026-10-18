/* Shipyard · Corp projects history: seven Chart.js graphs built from the page's events
   (services/projectbooks.py). Interval and date range change in the browser, no reload. */
(function () {
    "use strict";

    var node = document.getElementById("books-data");
    if (!node || !window.Chart) { return; }
    var B = JSON.parse(node.textContent);
    var DAY = 86400000;
    var KIND_COLOURS = { ore: "#ffd75e", moon: "#b197e6", ice: "#8adaff", item: "#75d39a", scan: "#f28b94", abyssal: "#ffa94d" };
    var TEXT = "#d7dfea", MUTED = "#8da2c0", GRID = "rgba(255,255,255,.07)";
    var charts = {};
    var state = { interval: "week", custom: 3, from: null, to: null };

    function isk(v) {
        var a = Math.abs(v);
        if (a >= 1e9) { return (v / 1e9).toFixed(2) + " B"; }
        if (a >= 1e6) { return (v / 1e6).toFixed(1) + " M"; }
        if (a >= 1e3) { return (v / 1e3).toFixed(0) + " k"; }
        return v.toFixed(0);
    }
    function alpha(hex, a) {
        var n = parseInt(hex.slice(1), 16);
        return "rgba(" + (n >> 16) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
    }
    function t(s) { return new Date(s.length <= 16 ? s + ":00Z" : s).getTime(); }
    function dayStart(ms) { var d = new Date(ms); return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()); }
    function iso(ms) { return new Date(ms).toISOString().slice(0, 10); }
    function short(ms) { return iso(ms).slice(5); }

    // ---- preferences (per browser, optional)
    try {
        var saved = JSON.parse(window.localStorage.getItem("shipyard.projects.books") || "{}");
        if (saved.interval) { state.interval = saved.interval; }
        if (saved.custom) { state.custom = saved.custom; }
    } catch (e) { /* storage blocked: defaults */ }
    function save() {
        try { window.localStorage.setItem("shipyard.projects.books", JSON.stringify({ interval: state.interval, custom: state.custom })); } catch (e) { /* ignore */ }
    }

    // ---- the event lists with times parsed once
    var pays = B.payouts.map(function (r) {
        return { t: t(r[0]), kind: r[1], project: r[2], member: r[3], units: r[4], isk: r[5], m3: r[6], est: r[7] === 1, asis: r[8], reproc: r[9], material: r[10] };
    });
    var funding = B.funding.map(function (r) { return { t: t(r[0]), amount: r[1] }; });
    var matches = B.matches.map(function (r) { return { t: t(r[0]), name: r[1], revenue: r[2], cost: r[3] }; });
    var stockEv = B.stock.map(function (r) { return { t: t(r[0]), delta: r[1] }; });
    var allTimes = pays.map(function (e) { return e.t; }).concat(funding.map(function (e) { return e.t; }), matches.map(function (e) { return e.t; }));
    var firstDay = allTimes.length ? dayStart(Math.min.apply(null, allTimes)) : dayStart(Date.now());
    var lastDay = dayStart(Date.now());

    // ---- buckets
    function buckets() {
        var from = state.from !== null ? state.from : firstDay;
        var to = state.to !== null ? state.to : lastDay;
        if (to < from) { to = from; }
        var list = [];
        if (state.interval === "day") {
            for (var d = from; d <= to; d += DAY) { list.push({ start: d, end: d + DAY, label: short(d) }); }
        } else if (state.interval === "week") {
            var wd = (new Date(from).getUTCDay() + 6) % 7;  // Monday = 0
            for (var w = from - wd * DAY; w <= to; w += 7 * DAY) { list.push({ start: w, end: w + 7 * DAY, label: "wk " + short(w) }); }
        } else {
            var n = Math.max(1, state.custom) * DAY;
            for (var c = from; c <= to; c += n) {
                var e = Math.min(c + n, to + DAY);
                list.push({ start: c, end: e, label: short(c) + (e - c > DAY ? "–" + short(e - DAY) : "") });
            }
        }
        return { list: list, from: from, to: to + DAY };
    }
    function index(bk, ms) {
        for (var i = 0; i < bk.list.length; i++) { if (ms >= bk.list[i].start && ms < bk.list[i].end) { return i; } }
        return -1;
    }
    function zeros(n) { var a = []; for (var i = 0; i < n; i++) { a.push(0); } return a; }

    // ---- drawing
    function draw(id, config) {
        if (charts[id]) { charts[id].destroy(); }
        var el = document.getElementById(id);
        if (!el) { return; }
        charts[id] = new Chart(el, config);
    }
    function moneyAxis(stacked, extra) {
        var a = { stacked: !!stacked, ticks: { color: MUTED, callback: function (v) { return isk(v); } }, grid: { color: GRID } };
        for (var k in (extra || {})) { a[k] = extra[k]; }
        return a;
    }
    function base(labels, datasets, opts) {
        opts = opts || {};
        return {
            type: opts.type || "bar",
            data: { labels: labels, datasets: datasets },
            options: {
                responsive: true, interaction: { mode: "index", intersect: false }, indexAxis: opts.indexAxis || "x",
                plugins: {
                    legend: { labels: { color: TEXT, boxWidth: 12 } },
                    tooltip: { callbacks: { label: opts.label || function (c) { return c.dataset.label + ": " + isk(c.parsed.y); } } }
                },
                scales: opts.scales || { x: { stacked: !!opts.stacked, ticks: { color: MUTED }, grid: { color: GRID } }, y: moneyAxis(opts.stacked) }
            }
        };
    }

    function render() {
        var bk = buckets();
        var labels = bk.list.map(function (b) { return b.label; });
        var n = labels.length;
        var kinds = Object.keys(B.kinds).filter(function (k) { return pays.some(function (e) { return e.kind === k; }); });

        // 1 · paid to members, by kind, estimated lighter
        var sets1 = [];
        kinds.forEach(function (k) {
            var solid = zeros(n), est = zeros(n);
            pays.forEach(function (e) { if (e.kind !== k) { return; } var i = index(bk, e.t); if (i < 0) { return; } if (e.est) { est[i] += e.isk; } else { solid[i] += e.isk; } });
            var col = KIND_COLOURS[k] || "#9ad0f5";
            sets1.push({ label: B.kinds[k], data: solid, backgroundColor: col, stack: "s" });
            if (est.some(function (v) { return v; })) { sets1.push({ label: B.kinds[k] + " (estimated)", data: est, backgroundColor: alpha(col, 0.35), borderColor: col, borderWidth: 1, stack: "s" }); }
        });
        draw("books-paid", base(labels, sets1, { stacked: true }));

        // 2 · money in and out of projects, and the pool
        var put = zeros(n), back = zeros(n), paid = zeros(n), pool = zeros(n);
        funding.forEach(function (f) { var i = index(bk, f.t); if (i < 0) { return; } if (f.amount < 0) { put[i] += f.amount; } else { back[i] += f.amount; } });
        pays.forEach(function (e) { var i = index(bk, e.t); if (i >= 0) { paid[i] -= e.isk; } });
        bk.list.forEach(function (b, i) {
            var p = 0;
            funding.forEach(function (f) { if (f.t < b.end) { p += -f.amount; } });
            pays.forEach(function (e) { if (e.t < b.end) { p -= e.isk; } });
            pool[i] = p;
        });
        draw("books-flow", base(labels, [
            { label: "Put into projects", data: put, backgroundColor: "#dc3545", stack: "s" },
            { label: "Refunded on closing", data: back, backgroundColor: "#198754", stack: "s" },
            { label: "Paid to members", data: paid, backgroundColor: "#ffa94d", stack: "s" },
            { label: "Open in projects", data: pool, type: "line", borderColor: "#4cc3ff", backgroundColor: "transparent", borderWidth: 2, tension: 0.2, yAxisID: "y" }
        ], { stacked: true }));

        // 3 · running totals from the start of the range
        var cPaid = zeros(n), cSold = zeros(n), cCost = zeros(n);
        bk.list.forEach(function (b, i) {
            pays.forEach(function (e) { if (e.t >= bk.from && e.t < b.end) { cPaid[i] += e.isk; } });
            matches.forEach(function (m) { if (m.t >= bk.from && m.t < b.end) { cSold[i] += m.revenue; cCost[i] += m.cost; } });
        });
        draw("books-cumulative", base(labels, [
            { label: "Paid to members", data: cPaid, borderColor: "#ffa94d", backgroundColor: "transparent", borderWidth: 2, tension: 0.2 },
            { label: "Sold, matched to deliveries", data: cSold, borderColor: "#198754", backgroundColor: "transparent", borderWidth: 2, tension: 0.2 },
            { label: "Cost of what was sold", data: cCost, borderColor: "#dc3545", backgroundColor: "transparent", borderWidth: 2, borderDash: [5, 4], tension: 0.2 }
        ], { type: "line" }));

        // 4 · result of sold project goods, stock on hand at cost
        var rev = zeros(n), cost = zeros(n), profit = zeros(n), stock = zeros(n);
        matches.forEach(function (m) { var i = index(bk, m.t); if (i < 0) { return; } rev[i] += m.revenue; cost[i] -= m.cost; profit[i] += m.revenue - m.cost; });
        bk.list.forEach(function (b, i) { var s = 0; stockEv.forEach(function (e) { if (e.t < b.end) { s += e.delta; } }); stock[i] = s; });
        var cfg4 = base(labels, [
            { label: "Revenue", data: rev, backgroundColor: "#198754", stack: "s" },
            { label: "Cost (what projects paid for it)", data: cost, backgroundColor: "#dc3545", stack: "s" },
            { label: "Profit", data: profit, type: "line", borderColor: "#4cc3ff", backgroundColor: "transparent", borderWidth: 2, tension: 0.2 },
            { label: "Stock on hand, at cost", data: stock, type: "line", borderColor: "#ffd75e", backgroundColor: "transparent", borderWidth: 2, borderDash: [4, 3], tension: 0.2, yAxisID: "y2" }
        ], { stacked: true });
        cfg4.options.scales.y2 = moneyAxis(false, { position: "right", grid: { drawOnChartArea: false } });
        draw("books-result", cfg4);
        var sn = document.getElementById("books-stock-now");
        if (sn) {
            sn.textContent = B.has_sales
                ? "Stock from projects not sold yet: " + isk(B.stock_now.cost) + " at cost, " + isk(B.stock_now.value) + " at today's Jita buy."
                : "No market transactions of the corp stored yet: the first hourly read after the release fills this.";
        }

        // 5 · margin per material in the range
        var mats = {};
        pays.forEach(function (e) {
            if (e.t < bk.from || e.t >= bk.to || !e.asis) { return; }
            var m = mats[e.material] || (mats[e.material] = { paid: 0, asis: 0, reproc: 0 });
            m.paid += e.isk; m.asis += e.asis; m.reproc += e.reproc;
        });
        var names = Object.keys(mats).sort(function (a, b) { return mats[b].paid - mats[a].paid; });
        var pAsis = names.map(function (k) { return mats[k].asis ? 100 * mats[k].paid / mats[k].asis : 0; });
        var pRep = names.map(function (k) { return mats[k].reproc ? 100 * mats[k].paid / mats[k].reproc : 0; });
        draw("books-margin", base(names, [
            { label: "Paid as % of value as delivered", data: pAsis, backgroundColor: "#9ad0f5" },
            { label: "Paid as % of reprocessed value", data: pRep, backgroundColor: "#b197e6" }
        ], {
            indexAxis: "y",
            label: function (c) {
                var m = mats[names[c.dataIndex]];
                var v = c.datasetIndex === 0 ? m.asis : m.reproc;
                return c.dataset.label + ": " + c.parsed.x.toFixed(0) + " % (paid " + isk(m.paid) + " for " + isk(v) + ")";
            },
            scales: {
                x: { ticks: { color: MUTED, callback: function (v) { return v + " %"; } }, grid: { color: GRID }, suggestedMax: 110 },
                y: { ticks: { color: MUTED }, grid: { color: GRID } }
            }
        }));

        // 6 · volume delivered
        var sets6 = [];
        kinds.forEach(function (k) {
            var v = zeros(n);
            pays.forEach(function (e) { if (e.kind !== k) { return; } var i = index(bk, e.t); if (i >= 0) { v[i] += e.m3; } });
            if (v.some(function (x) { return x; })) { sets6.push({ label: B.kinds[k], data: v, backgroundColor: KIND_COLOURS[k] || "#9ad0f5", stack: "s" }); }
        });
        var cfg6 = base(labels, sets6, { stacked: true, label: function (c) { return c.dataset.label + ": " + Math.round(c.parsed.y).toLocaleString() + " m³"; } });
        cfg6.options.scales.y.ticks.callback = function (v) { return v >= 1e6 ? (v / 1e6).toFixed(1) + " M m³" : v >= 1e3 ? (v / 1e3).toFixed(0) + " k m³" : v + " m³"; };
        draw("books-volume", cfg6);

        // 7 · members taking part
        var who = bk.list.map(function () { return {}; }), earned = zeros(n);
        pays.forEach(function (e) { var i = index(bk, e.t); if (i < 0) { return; } who[i][e.member] = true; earned[i] += e.isk; });
        var count = who.map(function (o) { return Object.keys(o).length; });
        var avg = count.map(function (c, i) { return c ? earned[i] / c : 0; });
        var cfg7 = base(labels, [
            { label: "Members who delivered", data: count, backgroundColor: "#4cc3ff", yAxisID: "y" },
            { label: "Average earned per member", data: avg, type: "line", borderColor: "#ffd75e", backgroundColor: "transparent", borderWidth: 2, tension: 0.2, yAxisID: "y2" }
        ], {
            label: function (c) { return c.dataset.label + ": " + (c.datasetIndex === 0 ? c.parsed.y : isk(c.parsed.y)); },
            scales: {
                x: { ticks: { color: MUTED }, grid: { color: GRID } },
                y: { beginAtZero: true, ticks: { color: MUTED, precision: 0 }, grid: { color: GRID } },
                y2: moneyAxis(false, { position: "right", grid: { drawOnChartArea: false } })
            }
        });
        draw("books-members", cfg7);
    }

    // ---- controls
    var group = document.getElementById("books-interval");
    var customWrap = document.getElementById("books-custom-wrap");
    var custom = document.getElementById("books-custom");
    var from = document.getElementById("books-from");
    var to = document.getElementById("books-to");
    function sync() {
        group.querySelectorAll("button").forEach(function (b) { b.classList.toggle("active", b.dataset.interval === state.interval); });
        customWrap.hidden = state.interval !== "custom";
        custom.value = state.custom;
        from.value = iso(state.from !== null ? state.from : firstDay);
        to.value = iso(state.to !== null ? state.to : lastDay);
    }
    group.addEventListener("click", function (e) {
        var b = e.target.closest("button[data-interval]");
        if (!b) { return; }
        state.interval = b.dataset.interval; save(); sync(); render();
    });
    custom.addEventListener("change", function () { state.custom = Math.max(1, Math.min(90, parseInt(custom.value, 10) || 1)); save(); sync(); render(); });
    from.addEventListener("change", function () { state.from = from.value ? Date.parse(from.value + "T00:00:00Z") : null; render(); });
    to.addEventListener("change", function () { state.to = to.value ? Date.parse(to.value + "T00:00:00Z") : null; render(); });
    document.getElementById("books-reset").addEventListener("click", function () { state.from = null; state.to = null; sync(); render(); });
    sync();
    render();
})();
