/* Shipyard scrapmetal tab: DataTable + group / variant filters, favourable switch, search */
(function ($) {
    "use strict";

    $(function () {
        var el = document.getElementById("scrap-table");
        if (!el) { return; }
        var numCols = [];
        for (var i = parseInt(el.dataset.numFrom, 10); i <= parseInt(el.dataset.numTo, 10); i++) { numCols.push(i); }
        var table = $("#scrap-table").DataTable({
            order: [[8, "asc"]],
            paging: false,
            info: true,
            stateSave: true,
            dom: "rtip",
            columnDefs: [{ targets: numCols, type: "num" }]
        });

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
        remember("#scrap-variant", "shipyard.scrap.variants");
        remember("#scrap-group", "shipyard.scrap.groups");
        var fav = document.getElementById("scrap-favourable");
        try { fav.checked = window.localStorage.getItem("shipyard.scrap.favourable") === "1"; } catch (e) { /* ignore */ }

        $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
            if (settings.nTable.id !== "scrap-table") { return true; }
            var row = table.row(dataIndex).node();
            var variants = selected("#scrap-variant"), groups = selected("#scrap-group");
            if (variants.length && variants.indexOf(row.dataset.variant) < 0) { return false; }
            if (groups.length && groups.indexOf(row.dataset.group) < 0) { return false; }
            if (fav.checked && row.dataset.favourable !== "1") { return false; }
            return true;
        });

        function groupCount() {
            var n = selected("#scrap-group").length;
            $("#scrap-group-count").text(n ? n : "");
        }
        $("#scrap-text").val(table.search());
        $("#scrap-text").on("input search", function () { table.search(this.value).draw(); });
        $("#scrap-variant input, #scrap-group input").on("change", function () { groupCount(); table.draw(); });
        $(fav).on("change", function () {
            try { window.localStorage.setItem("shipyard.scrap.favourable", fav.checked ? "1" : "0"); } catch (e) { /* ignore */ }
            table.draw();
        });
        groupCount();
        table.draw();
    });
})(jQuery);
