/* Shipyard: a "Columns" dropdown that lets the member pick which columns a DataTable shows.
   The choice is remembered per browser (localStorage) as the list of hidden column keys; the
   header cells carry data-key so the list survives new or reordered columns. Hidden by default:
   opts.hiddenByDefault (for example m³, which the owner never looks at). Columns in opts.skip
   (the hidden Group column on the Scrapmetal tab) are not offered.
   After a change the table element gets the event "shipyard:columns" so a tab can react
   (the Scrapmetal tab recomputes its dragged widths). */
(function ($) {
    "use strict";

    window.shipyardColumnPicker = function (table, el, opts) {
        var container = document.querySelector(opts.container);
        if (!container) { return; }
        var hidden = null;
        try { hidden = JSON.parse(window.localStorage.getItem(opts.storageKey)); } catch (e) { hidden = null; }
        if (!Array.isArray(hidden)) { hidden = (opts.hiddenByDefault || []).slice(); }
        var skip = opts.skip || [];
        var columns = [];
        table.columns().every(function (i) {
            var th = this.header();
            var key = th.dataset.key;
            if (!key || skip.indexOf(key) >= 0) { return; }
            columns.push({ index: i, key: key, label: $(th).clone().children(".shipyard-resizer").remove().end().text().trim() || key });
        });
        function save() {
            try { window.localStorage.setItem(opts.storageKey, JSON.stringify(hidden)); } catch (e) { /* ignore */ }
        }
        function apply() {
            columns.forEach(function (c) { table.column(c.index).visible(hidden.indexOf(c.key) < 0, false); });
            table.columns.adjust().draw(false);
            $(el).trigger("shipyard:columns");
        }
        var id = (el.id || "table") + "-columns";
        var $menu = $('<ul class="dropdown-menu p-2 shipyard-columns-menu" aria-labelledby="' + id + '"></ul>');
        columns.forEach(function (c) {
            var cid = id + "-" + c.key;
            var $li = $('<li class="form-check"></li>');
            var $in = $('<input class="form-check-input" type="checkbox">').attr("id", cid).prop("checked", hidden.indexOf(c.key) < 0);
            var $lab = $('<label class="form-check-label"></label>').attr("for", cid).text(c.label);
            $in.on("change", function () {
                var at = hidden.indexOf(c.key);
                if (this.checked && at >= 0) { hidden.splice(at, 1); }
                if (!this.checked && at < 0) { hidden.push(c.key); }
                save();
                apply();
            });
            $menu.append($li.append($in, $lab));
        });
        var $all = $('<button type="button" class="btn btn-link btn-sm p-0">Show all</button>').on("click", function () {
            hidden = [];
            save();
            $menu.find("input").prop("checked", true);
            apply();
        });
        $menu.append('<li><hr class="dropdown-divider"></li>').append($("<li></li>").append($all));
        var $btn = $('<button class="btn btn-outline-secondary btn-sm dropdown-toggle" type="button" data-bs-toggle="dropdown" data-bs-auto-close="outside" aria-expanded="false"><i class="fas fa-table-columns fa-fw"></i> Columns</button>').attr("id", id);
        $(container).addClass("dropdown").append($btn, $menu);
        apply();
    };
})(jQuery);

/* Shipyard: draggable column widths for a DataTable. Drag the handle on a header's right edge;
   double-click a handle to reset every column. Widths are remembered per browser (localStorage,
   opts.storageKey), keyed by the header's data-key (or its position when a table has none), so
   hidden and future columns do not shift them. Once anything has been dragged the table is laid
   out fixed: a drag changes only that column, and the table grows wider than the page when
   needed (the wrapper scrolls sideways). Listens for "shipyard:columns" to lay out again. */
(function ($) {
    "use strict";

    window.shipyardColumnResizer = function (table, el, opts) {
        var widths = {};
        try { widths = JSON.parse(window.localStorage.getItem(opts.storageKey) || "{}") || {}; } catch (e) { widths = {}; }
        function headers() { return $(el).find("thead th").get(); }
        function keyOf(th) { return th.dataset.key || ("c" + Array.prototype.indexOf.call(th.parentNode.children, th)); }
        function applyWidths() {
            var any = Object.keys(widths).length > 0, total = 0;
            el.classList.toggle("shipyard-fixed", any);
            el.classList.toggle("w-100", !any);  // Bootstrap's w-100 is !important and would beat the width set below
            headers().forEach(function (th) {
                var w = widths[keyOf(th)];
                th.style.width = w ? w + "px" : "";
                if (th.offsetParent !== null) { total += w || 0; }  // hidden columns do not count
            });
            el.style.width = any ? total + "px" : "";
        }
        function saveWidths() {
            try { window.localStorage.setItem(opts.storageKey, JSON.stringify(widths)); } catch (e) { /* ignore */ }
        }
        var justResized = false;
        headers().forEach(function (th) {
            var handle = document.createElement("span");
            handle.className = "shipyard-resizer";
            handle.title = "Drag to resize this column; double-click to reset all columns";
            th.appendChild(handle);
            handle.addEventListener("mousedown", function (e) {
                if (e.button !== 0) { return; }
                e.preventDefault();
                e.stopPropagation();
                if (!Object.keys(widths).length) {
                    // first drag: freeze every visible column at its current size so nothing else moves
                    headers().forEach(function (h) {
                        if (h.offsetParent !== null) { widths[keyOf(h)] = Math.round(h.getBoundingClientRect().width); }
                    });
                }
                var startX = e.pageX, startW = widths[keyOf(th)] || Math.round(th.getBoundingClientRect().width);
                handle.classList.add("is-active");
                document.body.classList.add("shipyard-resizing");
                function move(ev) {
                    widths[keyOf(th)] = Math.max(36, startW + ev.pageX - startX);
                    applyWidths();
                }
                function up() {
                    document.removeEventListener("mousemove", move);
                    document.removeEventListener("mouseup", up);
                    handle.classList.remove("is-active");
                    document.body.classList.remove("shipyard-resizing");
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
        $(el).on("shipyard:columns", applyWidths);
        applyWidths();
    };
})(jQuery);
