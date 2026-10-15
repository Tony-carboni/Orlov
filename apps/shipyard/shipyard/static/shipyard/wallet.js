/* Shipyard structure income: payers table and journal table as DataTables, type filter, search */
(function ($) {
    "use strict";

    $(function () {
        if (document.getElementById("payers-table")) {
            $("#payers-table").DataTable({ order: [[3, "desc"]], paging: false, info: false, dom: "rt", stateSave: true, columnDefs: [{ targets: 0, orderable: false }] });
            // the Count box: a change posts the small form around it, the page comes back with the figures redone
            $("#payers-table").on("change", ".payer-include", function () { this.form.submit(); });
        }
        var el = document.getElementById("journal-table");
        if (!el) { return; }
        var table = $("#journal-table").DataTable({
            order: [[0, "desc"]],
            paging: true,
            pageLength: 50,
            lengthMenu: [25, 50, 100, 250, 500],
            info: true,
            stateSave: true,
            dom: "rtilp",
            columnDefs: [{ targets: [2, 7], type: "num" }]
        });
        function selected(group) {
            return $(group + " input:checked").map(function () { return this.value; }).get();
        }
        try {
            var saved = JSON.parse(window.localStorage.getItem("shipyard.journal.types") || "[]");
            $("#journal-type input").each(function () { this.checked = saved.indexOf(this.value) >= 0; });
        } catch (e) { /* ignore */ }
        $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
            if (settings.nTable.id !== "journal-table") { return true; }
            var types = selected("#journal-type");
            var row = table.row(dataIndex).node();
            return !types.length || types.indexOf(row.dataset.type) >= 0;
        });
        $("#journal-type input").on("change", function () {
            try { window.localStorage.setItem("shipyard.journal.types", JSON.stringify(selected("#journal-type"))); } catch (e) { /* ignore */ }
            table.draw();
        });
        $("#journal-text").val(table.search());
        $("#journal-text").on("input search", function () { table.search(this.value).draw(); });
        window.shipyardColumnResizer(table, el, { storageKey: "shipyard.journal.widths" });
        window.shipyardColumnPicker(table, el, { container: "#journal-columns", storageKey: "shipyard.journal.columns", hiddenByDefault: ["balance"] });
        table.draw();
    });
})(jQuery);
