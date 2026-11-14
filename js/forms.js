/* Safarnama Diaries - connects the site's forms to the backend API.
   Any <form> whose action starts with /api/ is submitted with fetch(). */
(function () {
  "use strict";

  var css = ".form-status{margin-top:14px;border-radius:6px;font-size:.95rem}" +
    ".form-status p{margin:0;padding:10px 14px}" +
    ".form-status.success{background:#e6f4ea;color:#14532d;border:1px solid #86c99b}" +
    ".form-status.error{background:#fdecea;color:#7f1d1d;border:1px solid #e8a5a0}" +
    ".form-status.pending{background:#f1f1f1;color:#333;border:1px solid #ccc}" +
    ".form-status:empty{display:none}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function statusBox(form) {
    var box = form.parentNode.querySelector(".form-status[data-for='" + form.id + "']");
    if (!box) {
      if (!form.id) form.id = "form-" + Math.random().toString(36).slice(2, 8);
      box = document.createElement("div");
      box.className = "form-status";
      box.setAttribute("role", "status");
      box.setAttribute("aria-live", "polite");
      box.setAttribute("data-for", form.id);
      form.insertAdjacentElement("afterend", box);
    }
    return box;
  }

  function show(box, kind, lines) {
    box.className = "form-status " + kind;
    box.textContent = "";
    lines.forEach(function (text) {
      var p = document.createElement("p");
      p.textContent = text; // textContent: never interpret server text as HTML
      box.appendChild(p);
    });
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  document.querySelectorAll("form[action^='/api/']").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!form.reportValidity()) return;

      var box = statusBox(form);
      var btn = form.querySelector("button[type='submit']");
      var label = btn ? btn.innerHTML : "";
      if (btn) { btn.disabled = true; btn.textContent = "Sending..."; }
      show(box, "pending", ["Sending..."]);

      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "Accept": "application/json", "X-Requested-With": "fetch" }
      })
        .then(function (res) {
          return res.json().catch(function () { return {}; }).then(function (data) {
            return { ok: res.ok && data.ok, data: data };
          });
        })
        .then(function (r) {
          if (r.ok) {
            show(box, "success", [r.data.message || "Thank you!"]);
            form.reset();
          } else {
            var errs = r.data.errors ? Object.values(r.data.errors) : [];
            show(box, "error", errs.length ? errs : ["Something went wrong. Please try again."]);
          }
        })
        .catch(function () {
          show(box, "error", ["Could not reach the server. Please check your connection and try again."]);
        })
        .finally(function () {
          if (btn) { btn.disabled = false; btn.innerHTML = label; }
        });
    });
  });
})();
