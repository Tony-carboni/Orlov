/* Shipyard scrapmetal tab: DataTable + group / variant filters, favourable switch, search */
(function ($) {
    "use strict";

    $(function () {
        var el = document.getElementById("scrap-table");
        if (!el) { return; }
        var numCols = [];
        for (var i = parseInt(el.dataset.numFrom, 10); i <= parseInt(el.dataset.numTo, 10); i++) { numCols.push(i); }
        // Grouped like the in-game tree: the owner's folder order, then the names alphabetically as the game lists them,
        // so a line here is the same line in the client.
        // A header row per group is drawn whenever the table is ordered by the (hidden) group column;
        // sorting by another column gives a flat list again.
        var colCount = el.querySelectorAll("thead th").length;
        var table = $("#scrap-table").DataTable({
            order: [[0, "asc"], [1, "asc"]],
            paging: false,
            info: true,
            stateSave: false,
            autoWidth: false,
            dom: "rtip",
            columnDefs: [{ targets: numCols, type: "num" }, { targets: 0, visible: false }],
            drawCallback: function () {
                var api = this.api();
                var grouped = api.order().length && api.order()[0][0] === 0;
                var last = null;
                api.rows({ page: "current" }).nodes().each(function (row) {
                    $(row).toggleClass("scrap-grouped", !!grouped);
                    if (!grouped) { return; }
                    var g = row.dataset.group;
                    if (g !== last) {
                        $(row).before('<tr class="scrap-group-row"><td colspan="' + api.columns(":visible").count() + '"><i class="fas fa-folder-open fa-fw"></i> ' + $("<span>").text(g).html() + "</td></tr>");
                        last = g;
                    }
                });
            }
        });
        // the group header rows must disappear before the next draw lays the rows out again
        table.on("preDraw", function () { $("#scrap-table tbody tr.scrap-group-row").remove(); });

        // Column widths: drag the handle on a header's right edge; double-click a handle to reset every column.
        // Widths are remembered per browser (localStorage), keyed by the header's data-key so the hidden Group
        // column and future columns do not shift them. Once anything has been dragged the table is laid out
        // fixed, so a drag changes only that column and the table grows wider than the page when needed
        // (the wrapper scrolls sideways).
        var WIDTH_KEY = "shipyard.scrap.widths";
        var widths = {};
        try { widths = JSON.parse(window.localStorage.getItem(WIDTH_KEY) || "{}") || {}; } catch (e) { widths = {}; }
        function headers() { return $(el).find("thead th").get(); }
        function applyWidths() {
            var any = Object.keys(widths).length > 0, total = 0;
            el.classList.toggle("scrap-fixed", any);
            el.classList.toggle("w-100", !any);  // Bootstrap's w-100 is !important and would beat the width set below
            headers().forEach(function (th) {
                var w = widths[th.dataset.key];
                th.style.width = w ? w + "px" : "";
                total += w || 0;
            });
            // the table is exactly as wide as its columns, so the dragged edge follows the mouse
            // and nothing else moves; wider than the page means the wrapper scrolls sideways
            el.style.width = any ? total + "px" : "";
        }
        function saveWidths() {
            try { window.localStorage.setItem(WIDTH_KEY, JSON.stringify(widths)); } catch (e) { /* ignore */ }
        }
        var justResized = false;
        headers().forEach(function (th) {
            var handle = document.createElement("span");
            handle.className = "scrap-resizer";
            handle.title = "Drag to resize this column; double-click to reset all columns";
            th.appendChild(handle);
            handle.addEventListener("mousedown", function (e) {
                if (e.button !== 0) { return; }
                e.preventDefault();
                e.stopPropagation();
                if (!Object.keys(widths).length) {
                    // first drag: freeze every column at its current size so nothing else moves
                    headers().forEach(function (h) { widths[h.dataset.key] = Math.round(h.getBoundingClientRect().width); });
                }
                var startX = e.pageX, startW = widths[th.dataset.key] || Math.round(th.getBoundingClientRect().width);
                handle.classList.add("is-active");
                document.body.classList.add("scrap-resizing");
                function move(ev) {
                    widths[th.dataset.key] = Math.max(36, startW + ev.pageX - startX);
                    applyWidths();
                }
                function up() {
                    document.removeEventListener("mousemove", move);
                    document.removeEventListener("mouseup", up);
                    handle.classList.remove("is-active");
                    document.body.classList.remove("scrap-resizing");
                    saveWidths();
                    justResized = true;
                    window.setTimeout(function () { justResized = false; }, 0);
                }
                document.addEventListener("mousemove", move);
                document.addEventListener("mouseup", up);
            });
            handle.addEventListener("click", function (e) { e.stopPropagation(); });
            handle.addEventListener("dblclick", function (e) {
                e.preventDefault();
                e.stopPropagation();
                widths = {};
                saveWidths();
                applyWidths();
            });
        });
        // a click that ends a drag must not sort the column (DataTables listens on the header)
        el.querySelector("thead").addEventListener("click", function (e) {
            if (justResized) { e.stopPropagation(); e.preventDefault(); }
        }, true);
        applyWidths();
        // which columns to show: the member's choice, remembered per browser; m³ hidden until ticked.
        // The hidden Group column is not offered. After a change the dragged widths are laid out again.
        $(el).on("shipyard:columns", applyWidths);
        window.shipyardColumnPicker(table, el, { container: "#scrap-columns", storageKey: "shipyard.scrap.columns", hiddenByDefault: ["m3"], skip: ["group"] });

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
