/* Shipyard bargains tab: DataTable (client-side sort) over the rows the server filtered */
(function ($) {
    "use strict";

    $(function () {
        var el = document.getElementById("bargains-table");
        if (!el) { return; }
        var numCols = [];
        for (var i = parseInt(el.dataset.numFrom, 10); i <= parseInt(el.dataset.numTo, 10); i++) { numCols.push(i); }
        var table = $("#bargains-table").DataTable({
            order: [[8, "asc"]],
            paging: false,
            info: false,
            stateSave: false,
            autoWidth: false,
            dom: "rt",
            columnDefs: [{ targets: numCols, type: "num" }]
        });
        if (window.shipyardColumnPicker) {
            window.shipyardColumnPicker(table, el, { container: "#bargains-columns", storageKey: "shipyard.bargains.columns", hiddenByDefault: ["high52", "days"] });
        }
    });
})(jQuery);
