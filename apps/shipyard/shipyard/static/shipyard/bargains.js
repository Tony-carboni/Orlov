/* Shipyard bargains tab: DataTable (client-side sort) over the rows the server filtered, and the right-click menu
   (0.31.0): filter or ignore the row's category at any level of its market-group path, flag or ignore the item.
   Choices are saved on the server per member and the page reloads with them applied. */
(function ($) {
    "use strict";

    $(function () {
        var el = document.getElementById("bargains-table");
        if (!el) { return; }
        var table = null;
        if (!el.dataset.empty) {
            var numCols = [];
            for (var i = parseInt(el.dataset.numFrom, 10); i <= parseInt(el.dataset.numTo, 10); i++) { numCols.push(i); }
            table = $("#bargains-table").DataTable({
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
        }

        var form = document.getElementById("bargains-pref-form");
        var menu = document.getElementById("bargains-menu");
        if (!form || !menu) { return; }
        var csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;

        function pref(action, value) {
            var body = new URLSearchParams();
            body.set("action", action);
            body.set("value", value);
            return fetch(form.action, { method: "POST", headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" }, body: body, credentials: "same-origin" })
                .then(function (r) { if (!r.ok) { throw new Error("HTTP " + r.status); } return r.json(); })
                .then(function () { window.location.reload(); })
                .catch(function (e) { window.alert("That did not save: " + e.message); });
        }

        function withParam(key, value) {
            var url = new URL(window.location.href);
            if (value === null) { url.searchParams.delete(key); } else { url.searchParams.set(key, value); }
            return url.toString();
        }

        function esc(s) { return $("<span>").text(s).html(); }

        function item(label, icon, cls, handler) {
            var a = document.createElement("a");
            a.className = "dropdown-item small " + (cls || "");
            a.href = "#";
            a.innerHTML = '<i class="fas ' + icon + ' fa-fw"></i> ' + esc(label);
            a.addEventListener("click", function (ev) { ev.preventDefault(); hide(); handler(); });
            return a;
        }

        function header(text) {
            var h = document.createElement("h6");
            h.className = "dropdown-header small";
            h.textContent = text;
            return h;
        }

        function hide() { menu.style.display = "none"; menu.innerHTML = ""; }

        function show(row, x, y) {
            menu.innerHTML = "";
            var name = row.dataset.name, type = row.dataset.type, path = row.dataset.path || "";
            var levels = [];
            if (path) {
                var parts = path.split(" › ");
                for (var i = 0; i < parts.length; i++) { levels.push(parts.slice(0, i + 1).join(" › ")); }
            }
            menu.appendChild(header(name));
            if (row.dataset.starred) {
                menu.appendChild(item("Unflag item", "fa-star", "", function () { pref("unstar", type); }));
            } else {
                menu.appendChild(item("Flag item (shows under Mine)", "fa-star", "text-warning", function () { pref("star", type); }));
            }
            if (row.dataset.ignored) {
                menu.appendChild(item("Show item again", "fa-eye", "", function () { pref("unignore_type", type); }));
            } else {
                menu.appendChild(item("Ignore item", "fa-eye-slash", "", function () { pref("ignore_type", type); }));
            }
            if (levels.length) {
                menu.appendChild(header("Filter for category"));
                levels.forEach(function (lvl, i) {
                    var short = lvl.split(" › ").slice(-1)[0];
                    menu.appendChild(item(Array(i + 1).join("  ") + short, "fa-filter", "", function () { window.location.href = withParam("path", lvl); }));
                });
                menu.appendChild(header("Ignore category"));
                levels.forEach(function (lvl, i) {
                    var short = lvl.split(" › ").slice(-1)[0];
                    menu.appendChild(item(Array(i + 1).join("  ") + short, "fa-eye-slash", "", function () { pref("ignore_path", lvl); }));
                });
            }
            menu.style.display = "block";
            var w = menu.offsetWidth, h = menu.offsetHeight;
            var left = Math.min(x, window.scrollX + document.documentElement.clientWidth - w - 8);
            var top = Math.min(y, window.scrollY + document.documentElement.clientHeight - h - 8);
            menu.style.left = Math.max(0, left) + "px";
            menu.style.top = Math.max(0, top) + "px";
        }

        $("#bargains-table tbody").on("contextmenu", "tr[data-type]", function (ev) {
            ev.preventDefault();
            show(this, ev.pageX, ev.pageY);
        });
        document.addEventListener("click", function (ev) { if (!menu.contains(ev.target)) { hide(); } });
        document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { hide(); } });
        window.addEventListener("scroll", hide, { passive: true });

        // the chips above the table
        $("#bargains-chips").on("click", "a[data-pref]", function (ev) {
            ev.preventDefault();
            pref(this.dataset.pref, this.dataset.value);
        });
        $("#bargains-chips").on("click", "a[data-chip]", function (ev) {
            ev.preventDefault();
            if (this.dataset.chip === "path") { window.location.href = withParam("path", null); }
            if (this.dataset.chip === "ignored") {
                var url = new URL(window.location.href);
                window.location.href = url.searchParams.get("ignored") === "1" ? withParam("ignored", null) : withParam("ignored", "1");
            }
        });
    });
})(jQuery);
