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
            var cat = $("#filter-category").val();
            var hull = $("#filter-hull").val();
            var onlyComplete = $("#filter-complete").is(":checked");
            var onlyProfit = $("#filter-profitable").is(":checked");
            if (cat && row.dataset.category !== cat) { return false; }
            if (hull && row.dataset.hull !== hull) { return false; }
            if (onlyComplete && row.dataset.complete !== "1") { return false; }
            if (onlyProfit && !(parseFloat(row.dataset.profit) > 0)) { return false; }
            return true;
        });

        $("#filter-category, #filter-hull, #filter-complete, #filter-profitable").on("change", function () { table.draw(); });
        table.draw();

        $("#shipyard-table tbody").on("click", "tr", function (e) {
            if ($(e.target).closest("a").length) { return; }
            var href = this.dataset.href;
            if (href) { window.location = href; }
        });
    });
})(jQuery);
