/* Shipyard reprocessing tab: DataTable + kind / variant / ore-type filters + search */
(function ($) {
    "use strict";

    $(function () {
        var el = document.getElementById("repro-table");
        if (!el) { return; }
        var numCols = [];
        for (var i = parseInt(el.dataset.numFrom, 10); i <= parseInt(el.dataset.numTo, 10); i++) { numCols.push(i); }
        var table = $("#repro-table").DataTable({
            order: [[9, "asc"]],
            paging: false,
            info: true,
            stateSave: true,
            dom: "rtip",
            columnDefs: [{ targets: numCols, type: "num" }]
        });
        // which columns to show: the member's choice, remembered per browser; m³ hidden until ticked
        window.shipyardColumnResizer(table, el, { storageKey: "shipyard.repro.widths" });
        window.shipyardColumnPicker(table, el, { container: "#repro-columns", storageKey: "shipyard.repro.columns", hiddenByDefault: ["m3"] });

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
        remember("#repro-kind", "shipyard.repro.kinds");
        remember("#repro-variant", "shipyard.repro.variants");
        remember("#repro-family", "shipyard.repro.families");
        remember("#repro-rarity", "shipyard.repro.rarities");
        remember("#repro-area", "shipyard.repro.areas");

        $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
            if (settings.nTable.id !== "repro-table") { return true; }
            var row = table.row(dataIndex).node();
            var kinds = selected("#repro-kind"), variants = selected("#repro-variant"), families = selected("#repro-family");
            if (kinds.length && kinds.indexOf(row.dataset.kind) < 0) { return false; }
            if (variants.length && variants.indexOf(row.dataset.variant) < 0) { return false; }
            if (families.length && families.indexOf(row.dataset.family) < 0) { return false; }
            var rarities = selected("#repro-rarity"), areas = selected("#repro-area");
            // moon ore answers to the rarity buttons, everything else to the area buttons
            if (row.dataset.kind === "moon") {
                if (rarities.length && rarities.indexOf(row.dataset.rarity) < 0) { return false; }
                if (areas.length && !rarities.length) { return false; }
            } else {
                if (areas.length && areas.indexOf(row.dataset.area) < 0) { return false; }
                if (rarities.length && !areas.length) { return false; }
            }
            return true;
        });

        function familyCount() {
            var n = selected("#repro-family").length;
            $("#repro-family-count").text(n ? n : "");
        }
        $("#repro-text").val(table.search());
        $("#repro-text").on("input search", function () { table.search(this.value).draw(); });
        $("#repro-kind input, #repro-variant input, #repro-family input, #repro-rarity input, #repro-area input").on("change", function () { familyCount(); table.draw(); });
        familyCount();
        table.draw();
    });
})(jQuery);
