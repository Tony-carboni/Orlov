/* Shipyard "My business": four Chart.js charts from the page's JSON, two DataTables */
(function ($) {
    "use strict";

    // the dashboard's category colours, then a neutral run for the rest
    var COLOURS = {
        "Base": "#6c757d", "Navy": "#0d6efd", "Pirate": "#dc3545", "Trig": "#c0392b", "Edencom": "#17a2b8",
        "ORE": "#b8860b", "Other": "#495057", "Fuel": "#0dcaf0",
        "In": "#198754", "Out": "#dc3545", "Net": "#4cc3ff"
    };
    var RUN = ["#4cc3ff", "#8adaff", "#75d39a", "#ffd75e", "#f28b94", "#b197e6", "#ffa94d", "#9ad0f5"];

    function colour(label, i) { return COLOURS[label] || RUN[i % RUN.length]; }

    function isk(v) {
        var a = Math.abs(v);
        if (a >= 1e9) { return (v / 1e9).toFixed(2) + " B"; }
        if (a >= 1e6) { return (v / 1e6).toFixed(1) + " M"; }
        if (a >= 1e3) { return (v / 1e3).toFixed(0) + " k"; }
        return v.toFixed(0);
    }

    function draw(id, data, money) {
        var el = document.getElementById(id);
        if (!el || !window.Chart || !data || !data.labels.length) {
            if (el) { el.parentNode.insertAdjacentHTML("beforeend", '<div class="shipyard-k small">Nothing in this range.</div>'); el.remove(); }
            return;
        }
        var datasets = data.datasets.map(function (d, i) {
            var base = { label: d.label, data: d.data, backgroundColor: colour(d.label, i), borderColor: colour(d.label, i), stack: "s" };
            if (d.type === "line") { base.type = "line"; base.backgroundColor = "transparent"; base.borderWidth = 2; base.tension = 0.2; base.stack = undefined; }
            return base;
        });
        new Chart(el, {
            type: "bar",
            data: { labels: data.labels, datasets: datasets },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: { color: "#d7dfea" } },
                    tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + (money ? isk(c.parsed.y) : c.parsed.y); } } }
                },
                scales: {
                    x: { stacked: true, ticks: { color: "#8da2c0" }, grid: { color: "rgba(255,255,255,.06)" } },
                    y: { stacked: true, ticks: { color: "#8da2c0", callback: function (v) { return money ? isk(v) : v; } }, grid: { color: "rgba(255,255,255,.08)" } }
                }
            }
        });
    }

    $(function () {
        var node = document.getElementById("business-charts");
        if (node) {
            var charts = JSON.parse(node.textContent);
            draw("chart-sold-category", charts.sold_category, false);
            draw("chart-sold-hull", charts.sold_hull, false);
            draw("chart-produced-category", charts.produced_category, false);
            draw("chart-wallet", charts.wallet, true);
        }
        if (document.getElementById("sold-table")) {
            var sold = $("#sold-table").DataTable({ order: [[3, "desc"]], paging: false, info: false, dom: "rt", stateSave: true, autoWidth: false,
                columnDefs: [{ targets: [3, 4, 5, 6], type: "num" }] });
            $("#sold-text").on("input search", function () { sold.search(this.value).draw(); });
            if (window.shipyardColumnPicker) {
                window.shipyardColumnPicker(sold, document.getElementById("sold-table"), { container: "#sold-columns", storageKey: "shipyard.business.sold.columns", hiddenByDefault: [] });
            }
        }
        if (document.getElementById("produced-table")) {
            $("#produced-table").DataTable({ order: [[3, "desc"]], paging: false, info: false, dom: "rt", stateSave: true, autoWidth: false,
                columnDefs: [{ targets: [3, 4, 5, 6], type: "num" }] });
        }
    });
})(jQuery);
