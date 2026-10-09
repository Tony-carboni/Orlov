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
            columns.push({ index: i, key: key, label: $(th).clone().children(".scrap-resizer").remove().end().text().trim() || key });
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
