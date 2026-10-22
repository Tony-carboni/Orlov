/* Shipyard "LP log": one Chart.js chart, earned above the axis and spent below, per corporation */
(function () {
    "use strict";
    var RUN = ["#4cc3ff", "#75d39a", "#ffd75e", "#f28b94", "#b197e6", "#ffa94d", "#9ad0f5", "#8adaff"];

    function draw(id, data) {
        var el = document.getElementById(id);
        if (!el || !window.Chart || !data || !data.labels.length) {
            if (el) { el.parentNode.insertAdjacentHTML("beforeend", '<div class="shipyard-k small">Nothing in this range.</div>'); el.remove(); }
            return;
        }
        var datasets = data.datasets.map(function (d, i) {
            var c = RUN[Math.floor(i / 2) % RUN.length];
            return { label: d.label, data: d.data, backgroundColor: c, borderColor: c, stack: "s", hidden: d.data.every(function (v) { return v === 0; }) };
        });
        new Chart(el, {
            type: "bar",
            data: { labels: data.labels, datasets: datasets },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: "#d7dfea" } } },
                scales: {
                    x: { stacked: true, ticks: { color: "#8da2c0" }, grid: { color: "rgba(255,255,255,.06)" } },
                    y: { stacked: true, ticks: { color: "#8da2c0" }, grid: { color: "rgba(255,255,255,.08)" } }
                }
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var node = document.getElementById("lplog-charts");
        if (node) { draw("chart-lp", JSON.parse(node.textContent).lp); }
    });
})();
