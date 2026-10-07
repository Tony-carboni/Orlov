/* Shipyard ship detail: ad-hoc simulation panel */
(function () {
    "use strict";

    function fmtIsk(v, digits) {
        if (v === null || v === undefined || isNaN(v)) { return "–"; }
        digits = digits === undefined ? 2 : digits;
        var a = Math.abs(v), s = v < 0 ? "-" : "";
        if (a >= 1e9) { return s + (a / 1e9).toFixed(digits) + " B"; }
        if (a >= 1e6) { return s + (a / 1e6).toFixed(digits) + " M"; }
        if (a >= 1e3) { return s + (a / 1e3).toFixed(digits) + " k"; }
        return s + a.toFixed(digits);
    }
    function fmtFull(v) {
        if (v === null || v === undefined) { return "no price"; }
        return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function fmtPct(v) { return (v === null || v === undefined) ? "–" : (v * 100).toFixed(1) + " %"; }
    function fmtNum(v) { return Math.round(v).toLocaleString("en-US"); }
    function fmtDuration(s) {
        if (!s) { return "–"; }
        var d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
        if (d) { return d + "d " + h + "h"; }
        if (h) { return h + "h " + (m < 10 ? "0" : "") + m + "m"; }
        return m + "m";
    }

    var panel = document.getElementById("sim-panel");
    if (!panel) { return; }
    var url = panel.dataset.url;
    var me = document.getElementById("sim-me"), te = document.getElementById("sim-te");
    var meVal = document.getElementById("sim-me-value"), teVal = document.getElementById("sim-te-value");
    var status = document.getElementById("sim-status");
    var result = document.getElementById("sim-result");
    var bomBody = document.querySelector("#bom-table tbody");
    var bomCaption = document.getElementById("bom-caption");
    var lastMaterials = [];
    document.querySelectorAll("#bom-table tbody tr[data-type-id]").forEach(function (tr) {
        lastMaterials.push({ name: tr.children[0].textContent.trim(), quantity: parseInt(tr.children[1].textContent.replace(/,/g, ""), 10) });
    });

    me.addEventListener("input", function () { meVal.textContent = me.value; });
    te.addEventListener("input", function () { teVal.textContent = te.value; });

    function setK(k, html) {
        var el = result.querySelector('[data-k="' + k + '"]');
        if (el) { el.innerHTML = html; }
    }

    function run() {
        var params = new URLSearchParams();
        params.set("me", me.value);
        params.set("te", te.value);
        params.set("facility", document.getElementById("sim-facility").value);
        var bpc = document.getElementById("sim-bpc").value.trim();
        var tag = document.getElementById("sim-tag").value.trim();
        if (bpc) { params.set("bpc", bpc); }
        if (tag) { params.set("tag", tag); }
        var useLp = document.getElementById("sim-use-lp");
        if (!useLp.disabled) { params.set("use_lp", useLp.checked ? "1" : "0"); }
        status.textContent = "calculating…";
        fetch(url + "?" + params.toString(), { credentials: "same-origin" })
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (!d.ok) { status.textContent = d.error || "failed"; return; }
                status.textContent = d.source === "snapshot" ? "from stored data" : "live from EVE Ref";
                setK("material_cost", fmtIsk(d.material_cost));
                setK("job_cost", fmtIsk(d.job_cost));
                setK("bpc_cost", fmtIsk(d.bpc_cost) + (d.bpc_source === "lp" ? ' <sup class="text-warning">LP</sup>' : ""));
                setK("tag_cost", fmtIsk(d.tag_cost));
                setK("fees", fmtIsk(d.sales_tax + d.broker_fee));
                setK("total_cost", fmtIsk(d.total_cost));
                var cls = d.net_profit === null ? "text-muted" : (d.net_profit > 0 ? "text-success" : "text-danger");
                setK("net_profit", '<strong class="' + cls + '">' + fmtIsk(d.net_profit) + '</strong> <span class="small text-muted" data-k="margin">(' + fmtPct(d.margin) + ')</span>');
                setK("time", fmtDuration(d.time_seconds));
                bomCaption.textContent = "ME " + d.me + " · TE " + d.te + " · " + (d.facility || "–");
                bomBody.innerHTML = "";
                lastMaterials = d.materials;
                d.materials.forEach(function (m) {
                    var tr = document.createElement("tr");
                    tr.innerHTML = '<td><img src="https://images.evetech.net/types/' + m.type_id + '/icon?size=32" width="20" height="20" class="me-1" alt="">' + m.name + "</td>" +
                        '<td class="text-end">' + fmtNum(m.quantity) + "</td>" +
                        '<td class="text-end">' + (m.unit_price === null ? '<span class="text-warning">no price</span>' : fmtFull(m.unit_price)) + "</td>" +
                        '<td class="text-end">' + fmtIsk(m.cost) + "</td>" +
                        '<td class="text-end">' + fmtNum(m.volume) + "</td>";
                    bomBody.appendChild(tr);
                });
                document.getElementById("bom-total").textContent = fmtIsk(d.material_cost);
                document.getElementById("bom-volume").textContent = fmtNum(d.material_volume);
            })
            .catch(function () { status.textContent = "request failed"; });
    }

    document.getElementById("sim-run").addEventListener("click", function (e) { e.preventDefault(); run(); });
    document.getElementById("sim-reset").addEventListener("click", function (e) {
        e.preventDefault();
        me.value = 0; te.value = 0; meVal.textContent = "0"; teVal.textContent = "0";
        document.getElementById("sim-bpc").value = ""; document.getElementById("sim-tag").value = "";
        var useLp = document.getElementById("sim-use-lp");
        if (!useLp.disabled) { useLp.checked = panel.dataset.useLp === "1"; }
        run();
    });

    document.getElementById("copy-multibuy").addEventListener("click", function (e) {
        e.preventDefault();
        var text = lastMaterials.map(function (m) { return m.name + " " + Math.ceil(m.quantity); }).join("\n");
        navigator.clipboard.writeText(text).then(function () { status.textContent = "multibuy list copied"; });
    });
})();
