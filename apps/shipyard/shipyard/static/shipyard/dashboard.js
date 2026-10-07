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
            var cats = selectedCategories();
            var hull = $("#filter-hull").val();
            var onlyComplete = $("#filter-complete").is(":checked");
            var onlyProfit = $("#filter-profitable").is(":checked");
            if (cats.length && cats.indexOf(row.dataset.category) < 0) { return false; }
            if (hull && row.dataset.hull !== hull) { return false; }
            if (onlyComplete && row.dataset.complete !== "1") { return false; }
            if (onlyProfit && !(parseFloat(row.dataset.profit) > 0)) { return false; }
            return true;
        });

        // type buttons: any number may be ticked; none ticked means all types. Remembered per browser.
        function selectedCategories() {
            return $("#filter-category input:checked").map(function () { return this.value; }).get();
        }
        try {
            var saved = JSON.parse(window.localStorage.getItem("shipyard.categories") || "[]");
            $("#filter-category input").each(function () { this.checked = saved.indexOf(this.value) >= 0; });
        } catch (e) { /* storage unavailable: start with all types */ }
        $("#filter-category input").on("change", function () {
            try { window.localStorage.setItem("shipyard.categories", JSON.stringify(selectedCategories())); } catch (e) { /* ignore */ }
        });

        $("#filter-category input, #filter-hull, #filter-complete, #filter-profitable").on("change", function () { table.draw(); });
        table.draw();

        $("#shipyard-table tbody").on("click", "tr", function (e) {
            if ($(e.target).closest("a").length) { return; }
            var href = this.dataset.href;
            if (href) { window.location = href; }
        });
    });
})(jQuery);
