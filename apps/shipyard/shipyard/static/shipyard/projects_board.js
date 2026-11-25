/* Shipyard Projects page (0.41.1): search and tick filters on the running projects and on the ore prices, in the
   Reprocessing tab's style; the ticks are remembered in this browser. A family's header row stays as long as one of
   its rows is shown. */
(function ($) {
    "use strict";

    function selected(group) {
        return $(group + " input:checked").map(function () { return this.value; }).get();
    }

    function remember(group, key) {
        try {
            var saved = JSON.parse(window.localStorage.getItem(key) || "[]");
            $(group + " input").each(function () { this.checked = saved.indexOf(this.value) >= 0; });
        } catch (e) { /* storage unavailable */ }
        $(group + " input").on("change", function () {
            try { window.localStorage.setItem(key, JSON.stringify(selected(group))); } catch (e) { /* ignore */ }
        });
    }

    function rememberSwitch(id, key) {
        var el = $(id);
        try { el.prop("checked", window.localStorage.getItem(key) === "1"); } catch (e) { /* ignore */ }
        el.on("change", function () {
            try { window.localStorage.setItem(key, this.checked ? "1" : "0"); } catch (e) { /* ignore */ }
        });
    }

    function applyProjects() {
        var text = ($("#pb-text").val() || "").toLowerCase().trim();
        var kinds = selected("#pb-kind"), families = selected("#pb-family");
        var onlyNearly = $("#pb-nearly").is(":checked"), hideMissing = $("#pb-missing").is(":checked");
        var visibleFamilies = {};
        $("#pb-table tbody tr.pb-row").each(function () {
            var d = this.dataset, show = true;
            if (kinds.length && kinds.indexOf(d.kind) < 0) { show = false; }
            if (families.length && families.indexOf(d.family) < 0) { show = false; }
            if (onlyNearly && d.flag !== "nearly") { show = false; }
            if (hideMissing && d.flag === "missing") { show = false; }
            if (text && (d.text || "").indexOf(text) < 0) { show = false; }
            $(this).toggle(show);
            if (show) { visibleFamilies[d.family] = true; }
        });
        $("#pb-table tbody tr.pb-group-row").each(function () {
            var d = this.dataset, show = !!visibleFamilies[d.family];
            // with no text and no flag filter a family stays listed even when every grade is hidden, so the gap shows
            if (!show && !text && !onlyNearly && !hideMissing) {
                show = (!kinds.length || kinds.indexOf(d.kind) >= 0) && (!families.length || families.indexOf(d.family) >= 0);
            }
            $(this).toggle(show);
        });
    }

    function applyPrices() {
        var text = ($("#pr-text").val() || "").toLowerCase().trim();
        var kinds = selected("#pr-kind"), grades = selected("#pr-grade");
        var visibleKinds = {};
        $("#pr-table tbody tr.pr-row").each(function () {
            var d = this.dataset, show = true;
            if (kinds.length && kinds.indexOf(d.kind) < 0) { show = false; }
            if (grades.length && grades.indexOf(d.grade) < 0) { show = false; }
            if (text && (d.text || "").indexOf(text) < 0) { show = false; }
            $(this).toggle(show);
            if (show) { visibleKinds[d.kind] = true; }
        });
        $("#pr-table tbody tr.pb-group-row").each(function () { $(this).toggle(!!visibleKinds[this.dataset.kind]); });
    }

    $(function () {
        remember("#pb-kind", "shipyard.projects.kinds");
        remember("#pb-family", "shipyard.projects.families");
        rememberSwitch("#pb-nearly", "shipyard.projects.nearly");
        rememberSwitch("#pb-missing", "shipyard.projects.hideMissing");
        remember("#pr-kind", "shipyard.projects.priceKinds");
        remember("#pr-grade", "shipyard.projects.priceGrades");
        $("#pb-text").on("input search", applyProjects);
        $("#pb-kind input, #pb-family input, #pb-nearly, #pb-missing").on("change", applyProjects);
        $("#pr-text").on("input search", applyPrices);
        $("#pr-kind input, #pr-grade input").on("change", applyPrices);
        applyProjects();
        applyPrices();
    });
})(jQuery);
