/* Shipyard dashboard: DataTable + filters + row click */
(function ($) {
    "use strict";

    $(function () {
        var table = $("#shipyard-table").DataTable({
            order: [[4, "desc"]],
            paging: false,
            info: true,
            stateSave: true,
            language: { search: "Find ship:" },
            columnDefs: [{ targets: [4, 5, 6, 7, 8, 9, 10, 11, 12], type: "num" }]
        });

        // custom filters read the data-* attributes on each row
        $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
            if (settings.nTable.id !== "shipyard-table") { return true; }
            var row = table.row(dataIndex).node();
            var cats = selected("#filter-category");
            var hulls = selected("#filter-hull");
            var onlyComplete = $("#filter-complete").is(":checked");
            var onlyProfit = $("#filter-profitable").is(":checked");
            if (cats.length && cats.indexOf(row.dataset.category) < 0) { return false; }
            if (hulls.length && hulls.indexOf(row.dataset.hull) < 0) { return false; }
            if (onlyComplete && row.dataset.complete !== "1") { return false; }
            if (onlyProfit && !(parseFloat(row.dataset.profit) > 0)) { return false; }
            return true;
        });

        // type and hull buttons: any number may be ticked; none ticked means all. Remembered per browser.
        function selected(group) {
            return $(group + " input:checked").map(function () { return this.value; }).get();
        }
        function remember(group, key) {
            try {
                var saved = JSON.parse(window.localStorage.getItem(key) || "[]");
                $(group + " input").each(function () { this.checked = saved.indexOf(this.value) >= 0; });
            } catch (e) { /* storage unavailable: start with everything shown */ }
            $(group + " input").on("change", function () {
                try { window.localStorage.setItem(key, JSON.stringify(selected(group))); } catch (e) { /* ignore */ }
            });
        }
        remember("#filter-category", "shipyard.categories");
        remember("#filter-hull", "shipyard.hulls");

        $("#filter-category input, #filter-hull input, #filter-complete, #filter-profitable").on("change", function () { table.draw(); });
        table.draw();

        $("#shipyard-table tbody").on("click", "tr", function (e) {
            if ($(e.target).closest("a").length) { return; }
            var href = this.dataset.href;
            if (href) { window.location = href; }
        });
    });
})(jQuery);
