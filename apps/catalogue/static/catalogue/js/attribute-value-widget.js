/**
 * Attribute value widget switcher.
 * Listens for definition select changes and swaps the value input
 * via AJAX to match the selected definition's value_type.
 */
(function () {
  "use strict";

  var API = "/admin/catalogue-api/attribute-definition/";
  var cache = {};

  function fetchDefn(pk, cb) {
    if (cache[pk]) { cb(cache[pk]); return; }
    fetch(API + pk + "/", {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (d) { cache[pk] = d; cb(d); })
      .catch(function () {});
  }

  function esc(s) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(s || ""));
    return d.innerHTML;
  }

  /* Unfold class constants (from unfold/widgets.py) */
  var BASE =
    "border border-base-200 bg-white font-medium min-w-20 " +
    "placeholder-base-400 rounded-default shadow-xs " +
    "text-font-default-light text-sm " +
    "focus:outline-2 focus:-outline-offset-2 focus:outline-primary-600 " +
    "group-[.errors]:border-red-600 focus:group-[.errors]:outline-red-600 " +
    "dark:bg-base-900 dark:border-base-700 dark:text-font-default-dark " +
    "dark:group-[.errors]:border-red-500 dark:focus:group-[.errors]:outline-red-500 " +
    "dark:scheme-dark group-[.primary]:border-transparent " +
    "disabled:!bg-base-50 dark:disabled:!bg-base-800";

  var INPUT = BASE + " px-3 py-2 w-full";
  var SELECT = BASE + " px-3 py-2 w-full pr-8! appearance-none text-ellipsis";
  var TEXTAREA = BASE + " px-3 py-2 w-full appearance-none";
  var COLOR = BASE + " h-[38px] px-2 py-2 w-32";

  /* Exact CHECKBOX_CLASSES from unfold/widgets.py */
  var CHECKBOX =
    "appearance-none bg-white block border border-base-300 " +
    "h-4 min-w-4 relative rounded-[4px] shadow-xs w-4 " +
    "dark:bg-base-900 dark:border-base-700 " +
    "dark:checked:after:text-white " +
    "after:absolute after:content-['check\\_small'] after:flex! " +
    "after:h-4 after:items-center after:justify-center " +
    "after:leading-none after:material-symbols-outlined " +
    "after:-ml-px after:-mt-px after:text-white after:w-4 " +
    "dark:after:text-transparent " +
    "checked:bg-primary-600 checked:border-primary-600 " +
    "dark:checked:bg-primary-600 dark:checked:border-primary-600 " +
    "focus:ring-primary-500 focus:ring-2 focus:ring-offset-0";

  var CHEVRON =
    '<span class="material-symbols-outlined absolute pointer-events-none ' +
    'mr-[12px] right-0 text-base-400 top-1/2 hover:text-base-700 ' +
    'dark:text-base-500 dark:hover:text-base-200 -translate-y-1/2">' +
    "expand_more</span>";

  var INPUT_TYPE = {
    integer: "number", big_integer: "number", decimal: "number",
    float: "number", email: "email", url: "url",
    date: "date", time: "time", datetime: "datetime-local",
  };

  /* ── Build widgets ──────────────────────────────────────────── */

  function buildWidget(name, defn, cur) {
    var vt = defn.value_type;
    if (vt === "boolean") return buildSel(name, [["true", "Yes"], ["false", "No"]], cur);
    if (vt === "single_select") return buildSel(name, defn.options, cur);
    if (vt === "multi_select") return buildChecks(name, defn.options, cur);
    if (vt === "long_text") return buildTextarea(name, cur);
    if (vt === "color") return buildColor(name, cur);
    var it = INPUT_TYPE[vt] || "text";
    return buildInput(name, it, cur);
  }

  function buildInput(name, type, cur) {
    return '<div class="max-w-2xl relative w-full">' +
      '<input type="' + type + '" name="' + name +
      '" value="' + esc(cur) + '" class="' + INPUT + '"></div>';
  }

  function buildTextarea(name, cur) {
    return '<textarea name="' + name + '" class="' + TEXTAREA +
      '" rows="4">' + esc(cur) + '</textarea>';
  }

  function buildColor(name, cur) {
    return '<input type="color" name="' + name +
      '" value="' + (cur || "#000000") + '" class="' + COLOR + '">';
  }

  function buildSel(name, opts, cur) {
    var h = '<div class="relative max-w-2xl w-full"><select name="' + name +
      '" class="' + SELECT + '">';
    h += '<option value="">---------</option>';
    for (var i = 0; i < opts.length; i++) {
      var o = opts[i];
      var v = typeof o === "object" ? o.value : o;
      var l = typeof o === "object" ? o.label : o;
      h += '<option value="' + esc(v) + '"' +
        (String(v) === String(cur) ? " selected" : "") + '>' + esc(l) + '</option>';
    }
    return h + '</select>' + CHEVRON + '</div>';
  }

  function buildChecks(name, opts, cur) {
    var vals = cur ? String(cur).split(",") : [];
    var h = '<div class="flex flex-col gap-2">';
    for (var i = 0; i < opts.length; i++) {
      var o = opts[i];
      var v = typeof o === "object" ? o.value : o;
      var l = typeof o === "object" ? o.label : o;
      var ck = vals.indexOf(v) !== -1 ? " checked" : "";
      var id = name.replace(/-/g, "_") + "_" + i;
      h += '<label for="' + id + '" class="flex items-center gap-2 cursor-pointer">' +
        '<input type="checkbox" id="' + id + '" name="' + name +
        '" value="' + esc(v) + '"' + ck + ' class="' + CHECKBOX + '">' +
        '<span class="truncate text-sm">' + esc(l) + '</span></label>';
    }
    return h + '</div>';
  }

  /* ── Replace value widget ───────────────────────────────────── */

  function replaceValueWidget(valueEl, html) {
    var grow = valueEl.closest(".flex.flex-col.grow");
    if (!grow) return;
    var widgetEl = valueEl;
    while (widgetEl.parentElement && widgetEl.parentElement !== grow) {
      widgetEl = widgetEl.parentElement;
    }
    widgetEl.outerHTML = html;
  }

  /* ── Handle definition change ───────────────────────────────── */

  function onDefinitionChange(sel) {
    var pk = sel.value;
    if (!pk) return;
    var tr = sel.closest("tr");
    if (!tr) return;
    var vName = sel.name.replace(/-definition$/, "-value");
    var vEl = tr.querySelector('[name="' + vName + '"]');
    if (!vEl) return;
    fetchDefn(pk, function (defn) {
      replaceValueWidget(vEl, buildWidget(vName, defn, vEl.value));
    });
  }

  /* ── Bootstrap ──────────────────────────────────────────────── */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

  function start() {
    /* 1) Native change event delegation - works for plain <select> */
    document.addEventListener("change", function (e) {
      var sel = e.target;
      if (sel && sel.tagName === "SELECT" && sel.name && sel.name.endsWith("-definition")) {
        if (!sel.closest(".empty-form")) onDefinitionChange(sel);
      }
    });

    /* 2) Select2: bind select2:select via jQuery on the original
       <select>.  Use a short delay so Select2 has time to init. */
    setTimeout(function () {
      if (typeof django === "undefined" || !django.jQuery) return;
      var $ = django.jQuery;
      $(document).on("select2:select", 'select[name$="-definition"]', function () {
        if (!this.closest(".empty-form")) onDefinitionChange(this);
      });
    }, 500);

    /* 3) MutationObserver: re-bind select2:select on new rows */
    var observer = new MutationObserver(function () {
      if (typeof django === "undefined" || !django.jQuery) return;
      var $ = django.jQuery;
      $('select[name$="-definition"]:not(.avw-bound)').each(function () {
        $(this).addClass("avw-bound").on("select2:select", function () {
          if (!this.closest(".empty-form")) onDefinitionChange(this);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
})();
