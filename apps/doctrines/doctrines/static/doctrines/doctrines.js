/* Doctrines: expand a ship's fitting, copy the fitting text to the clipboard. */
(function () {
    "use strict";

    function toggle(row) {
        var target = document.getElementById(row.dataset.target);
        if (!target) { return; }
        var open = target.hasAttribute("hidden");
        if (open) { target.removeAttribute("hidden"); } else { target.setAttribute("hidden", ""); }
        row.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function copy(button) {
        var area = document.getElementById(button.dataset.copy);
        if (!area) { return; }
        var text = area.value;
        function done(ok) {
            var label = button.innerHTML;
            button.classList.add("is-done");
            button.innerHTML = ok ? '<i class="fas fa-check fa-fw"></i> Copied, paste it in the fitting window' : '<i class="fas fa-triangle-exclamation fa-fw"></i> Copy blocked, use "Open as text"';
            window.setTimeout(function () { button.classList.remove("is-done"); button.innerHTML = label; }, 2500);
        }
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
            return;
        }
        // older browsers: select the hidden textarea and use the old command
        try {
            area.style.position = "fixed"; area.style.left = "0"; area.style.opacity = "0.01";
            area.focus(); area.select();
            var ok = document.execCommand("copy");
            area.style.position = ""; area.style.left = ""; area.style.opacity = "";
            done(!!ok);
        } catch (e) { done(false); }
    }

    function pick(tab) {
        var group = tab.dataset.group;
        document.querySelectorAll('.doctrines-variant[data-group="' + group + '"]').forEach(function (b) {
            var on = b === tab;
            b.classList.toggle("active", on);
            b.setAttribute("aria-selected", on ? "true" : "false");
        });
        document.querySelectorAll('.doctrines-pane[data-group="' + group + '"]').forEach(function (p) {
            if (p.id === tab.dataset.pane) { p.removeAttribute("hidden"); } else { p.setAttribute("hidden", ""); }
        });
    }

    document.addEventListener("click", function (e) {
        var tab = e.target.closest(".doctrines-variant");
        if (tab) { e.preventDefault(); e.stopPropagation(); pick(tab); return; }
        var button = e.target.closest(".doctrines-copy");
        if (button) { e.preventDefault(); e.stopPropagation(); copy(button); return; }
        var row = e.target.closest("tr.doctrines-ship-row");
        if (row && !e.target.closest("a")) { toggle(row); }
    });

    // #fit-<id> in the address opens that ship
    if (window.location.hash && window.location.hash.indexOf("#fit-") === 0) {
        var row = document.querySelector('tr.doctrines-ship-row[data-target="' + window.location.hash.slice(1) + '"]');
        if (row) { toggle(row); row.scrollIntoView({ block: "start" }); }
    }
})();
