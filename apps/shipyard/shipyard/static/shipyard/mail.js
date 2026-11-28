/* Shipyard mail tab: the list (DataTable + character / folder / unread filters) and the reader pane */
(function ($) {
    "use strict";

    $(function () {
        var el = document.getElementById("mail-table");
        if (!el) { return; }
        var table = $("#mail-table").DataTable({
            order: [[0, "desc"]],
            paging: true,
            pageLength: 50,
            lengthChange: false,
            info: true,
            stateSave: false,
            dom: "rtip",
            columnDefs: [{ targets: 0, type: "num" }]
        });

        function selected(group) {
            return $(group + " input:checked").map(function () { return this.value; }).get();
        }
        var unread = document.getElementById("mail-unread"), sent = document.getElementById("mail-sent");

        $.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
            if (settings.nTable.id !== "mail-table") { return true; }
            var row = table.row(dataIndex).node();
            var chars = selected("#mail-char"), kinds = selected("#mail-kind");
            if (chars.length && chars.indexOf(row.dataset.char) < 0) { return false; }
            if (row.dataset.kind === "sent") { return sent.checked && !unread.checked; }
            if (kinds.length && kinds.indexOf(row.dataset.kind) < 0) { return false; }
            if (unread.checked && row.dataset.unread !== "1") { return false; }
            return true;
        });

        $("#mail-text").on("input search", function () { table.search(this.value).draw(); });
        $("#mail-char input, #mail-kind input").on("change", function () { table.draw(); });
        $(unread).add(sent).on("change", function () { table.draw(); });
        table.draw();

        var subject = document.getElementById("mail-subject"), meta = document.getElementById("mail-meta"), body = document.getElementById("mail-body");
        var current = null;

        function show(row) {
            if (current) { current.classList.remove("table-active"); }
            current = row;
            row.classList.add("table-active");
            subject.textContent = "Loading…";
            meta.textContent = "";
            body.textContent = "";
            fetch(row.dataset.url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
                .then(function (res) {
                    if (current !== row) { return; }
                    if (!res.ok || !res.d.ok) {
                        subject.textContent = "Could not load this mail";
                        meta.textContent = (res.d && res.d.error) || "EVE did not answer; try again in a minute.";
                        return;
                    }
                    subject.textContent = res.d.subject;
                    meta.textContent = "From " + res.d.from + " · to " + res.d.to.join(", ") + " · " + res.d.timestamp;
                    // body_html is built on the server from escaped text, <br> and http(s) links only
                    body.innerHTML = res.d.body_html || "<span class=\"shipyard-k\">(empty)</span>";
                    if (window.matchMedia("(max-width: 1199px)").matches) {
                        document.getElementById("mail-reader").scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                })
                .catch(function () {
                    if (current !== row) { return; }
                    subject.textContent = "Could not load this mail";
                    meta.textContent = "The connection failed; try again.";
                });
        }

        $("#mail-table tbody").on("click", "tr.mail-row", function () { show(this); });
    });
})(jQuery);
