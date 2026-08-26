from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.utils.html import format_html
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from unfold.widgets import BASE_CLASSES
from unfold.widgets import CHECKBOX_CLASSES
from unfold.widgets import COLOR_CLASSES
from unfold.widgets import INPUT_CLASSES
from unfold.widgets import SELECT_CLASSES
from unfold.widgets import TEXTAREA_CLASSES
from unfold.widgets import UnfoldAdminSelectWidget

from apps.catalogue.enums import UNITS_BY_DIMENSION
from apps.catalogue.enums import AttributeValueType
from apps.catalogue.enums import UnitDimension

if TYPE_CHECKING:
    from django.utils.safestring import SafeString

    from apps.catalogue.models.attribute import AttributeDefinition

# Custom classes for table cell inputs
_KV_INPUT = " ".join([*BASE_CLASSES, "px-3", "py-2", "w-full"])
_KV_SELECT = " ".join(
    [
        *BASE_CLASSES,
        "px-3",
        "py-2",
        "w-full",
        "pr-8!",
    ]
)

# Material Symbols icons (matching Unfold's inline delete style)
_DELETE_ICON = mark_safe(
    '<span class="material-symbols-outlined md-18 text-red-600 dark:text-red-500">'
    "delete</span>"
)
_ADD_ICON = mark_safe('<span class="material-symbols-outlined md-18">add</span>')


class KeyValueWidget(forms.Widget):
    template_name = ""

    class Media:
        css: dict[str, tuple[str, ...]] = {}

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> SafeString:
        pairs: list[tuple[str, str]] = []
        if value:
            if isinstance(value, str):
                try:
                    decoded = json.loads(value)
                except json.JSONDecodeError, TypeError:
                    decoded = {}
            else:
                decoded = value if isinstance(value, dict) else {}
            pairs = [(str(k), str(v)) for k, v in decoded.items()]

        pairs.append(("", ""))

        widget_id = (attrs or {}).get("id", f"id_{name}")
        container_id = f"{widget_id}_kv_container"

        row_template = (
            '<tr class="kv-row border-b border-base-200 dark:border-base-700">'
            '<td class="py-2 pl-2 w-1/2">'
            '<input type="text" name="{}" value="{}" id="{}"'
            ' class="{} kv-key rounded-l-default" placeholder="{}">'
            "</td>"
            '<td class="py-2 pl-2 w-1/2">'
            '<input type="text" name="{}" value="{}" id="{}"'
            ' class="{} kv-val" placeholder="{}">'
            "</td>"
            '<td class="py-2 w-12">'
            '<a href="#" class="deletelink kv-remove-btn cursor-pointer flex'
            " h-[38px] w-[38px] items-center justify-center rounded-default"
            " select-none transition-colors hover:bg-base-50"
            ' dark:hover:bg-base-800" title="{}">'
            "{}"
            "</a>"
            "</td>"
            "</tr>"
        )
        rows_html = format_html_join(
            "",
            row_template,
            (
                (
                    f"{name}__key__{idx}",
                    k,
                    f"{widget_id}_key_{idx}",
                    _KV_INPUT,
                    _("Key"),
                    f"{name}__val__{idx}",
                    v,
                    f"{widget_id}_val_{idx}",
                    _KV_INPUT,
                    _("Value"),
                    _("Remove row"),
                    _DELETE_ICON,
                )
                for idx, (k, v) in enumerate(pairs)
            ),
        )

        table_html = format_html(
            '<div id="{}" class="js-inline-admin-formset inline-group">'
            '<div class="tabular inline-related">'
            '<fieldset class="module border border-base-200'
            ' dark:border-base-700 rounded-default overflow-hidden">'
            '<div class="bg-base-50 dark:bg-base-800 px-4 py-3'
            ' border-b border-base-200 dark:border-base-700">'
            '<h3 class="text-sm font-semibold text-base-700'
            ' dark:text-base-300 m-0">{}</h3>'
            "</div>"
            '<table class="w-full">'
            "<thead>"
            '<tr class="border-b border-base-200 dark:border-base-700'
            ' bg-base-50 dark:bg-base-800">'
            '<th class="px-4 py-2 text-left text-xs font-medium'
            " text-base-500 dark:text-base-400 uppercase"
            ' tracking-wider">{}</th>'
            '<th class="px-4 py-2 text-left text-xs font-medium'
            " text-base-500 dark:text-base-400 uppercase"
            ' tracking-wider">{}</th>'
            '<th class="px-4 py-2 w-12"></th>'
            "</tr>"
            "</thead>"
            '<tbody id="{}" class="divide-y divide-base-200'
            ' dark:divide-base-700">{}</tbody>'
            "</table>"
            "</fieldset>"
            '<div class="mt-3 px-4">'
            '<a href="#" class="kv-add-btn inline-flex items-center'
            " gap-2 text-sm font-medium text-primary-600"
            " hover:text-primary-700 dark:text-primary-400"
            ' dark:hover:text-primary-300 transition-colors"'
            ' data-container="{}"'
            ' data-name="{}"'
            ' data-next="{}"'
            ' data-widget-id="{}">'
            "{} {}"
            "</a>"
            "</div>"
            "</div>"
            "</div>",
            container_id,
            _("Extra Attributes"),
            _("Key"),
            _("Value"),
            f"{widget_id}_kv_tbody",
            rows_html,
            f"{widget_id}_kv_tbody",
            name,
            len(pairs),
            widget_id,
            _ADD_ICON,
            _("Add another"),
        )

        script = format_html(
            """
<script>
(function() {{
  function kvInit() {{
    document.addEventListener('click', function(e) {{
      var btn = e.target.closest('.kv-remove-btn');
      if (!btn) return;
      e.preventDefault();
      var row = btn.closest('.kv-row');
      if (row) {{
        row.style.opacity = '0';
        row.style.transform = 'translateX(-10px)';
        row.style.transition = 'opacity 0.2s, transform 0.2s';
        setTimeout(function() {{ row.remove(); }}, 200);
      }}
    }});
    document.addEventListener('click', function(e) {{
      var btn = e.target.closest('.kv-add-btn');
      if (!btn) return;
      e.preventDefault();
      var tbodyId = btn.getAttribute('data-container');
      var baseName = btn.getAttribute('data-name');
      var next = parseInt(btn.getAttribute('data-next'), 10);
      btn.setAttribute('data-next', next + 1);
      var tbody = document.getElementById(tbodyId);
      var tr = document.createElement('tr');
      tr.className = 'kv-row border-b border-base-200 dark:border-base-700';
      tr.style.opacity = '0';
      tr.style.transform = 'translateY(-5px)';
      tr.innerHTML =
        '<td class="py-2 pl-2 w-1/2"><input type="text" name="'
        + baseName + '__key__' + next + '" class="{} kv-key'
        + ' rounded-l-default" placeholder="{}"></td>'
        + '<td class="py-2 pl-2 w-1/2"><input type="text" name="'
        + baseName + '__val__' + next + '" class="{} kv-val'
        + '" placeholder="{}"></td>'
        + '<td class="py-2 w-12"><a href="#" class="deletelink'
        + ' kv-remove-btn cursor-pointer flex h-[38px] w-[38px]'
        + ' items-center justify-center rounded-default select-none'
        + ' transition-colors hover:bg-base-50 dark:hover:bg-base-800"'
        + ' title="Remove row">'
        + 'TRASH_ICON_PLACEHOLDER'
        + '</a></td>';
      tbody.appendChild(tr);
      requestAnimationFrame(function() {{
        tr.style.transition = 'opacity 0.2s, transform 0.2s';
        tr.style.opacity = '1';
        tr.style.transform = 'translateY(0)';
      }});
    }});
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', kvInit);
  }} else {{
    kvInit();
  }}
}})();
</script>""",
            _KV_INPUT,
            _("Key"),
            _KV_INPUT,
            _("Value"),
        )
        # Replace placeholder with actual icon (avoids format_html escaping)
        icon_replacement = str(_DELETE_ICON)
        script = mark_safe(  # noqa: S308 - controlled HTML content
            str(script).replace("TRASH_ICON_PLACEHOLDER", icon_replacement)
        )

        return format_html("{}{}", table_html, script)

    def value_from_datadict(
        self,
        data: Any,
        files: Any,
        name: str,
    ) -> str:
        result: dict[str, str] = {}
        prefix_key = f"{name}__key__"
        prefix_val = f"{name}__val__"

        indices: list[int] = []
        for field_name in data:
            if field_name.startswith(prefix_key):
                try:
                    idx = int(field_name[len(prefix_key) :])
                    indices.append(idx)
                except ValueError:
                    pass

        for idx in sorted(indices):
            key = data.get(f"{prefix_key}{idx}", "").strip()
            val = data.get(f"{prefix_val}{idx}", "").strip()
            if key:
                result[key] = val

        return json.dumps(result)

    def value_omitted_from_data(
        self,
        data: Any,
        files: Any,
        name: str,
    ) -> bool:
        prefix_key = f"{name}__key__"
        return not any(k.startswith(prefix_key) for k in data)


class KeyValueField(forms.Field):
    widget = KeyValueWidget

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", _("Extra Attributes"))
        kwargs.setdefault(
            "help_text",
            _("Free-form key/value pairs. Leave the key blank to remove a row."),
        )
        super().__init__(**kwargs)

    def prepare_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError, TypeError:
                return {}
        return {}

    def to_python(self, value: Any) -> dict[str, str]:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError, TypeError:
                pass
        return {}

    def validate(self, value: Any) -> None:
        pass


_UNITS_JSON: str = json.dumps(
    {
        dim: [[sym, lbl] for sym, lbl in units]
        for dim, units in UNITS_BY_DIMENSION.items()
    },
    ensure_ascii=False,
)


class UnitSymbolWidget(UnfoldAdminSelectWidget):  # type: ignore[misc]
    def __init__(
        self, dimension_field_id: str = "id_unit_dimension", **kwargs: Any
    ) -> None:
        self._dim_field_id = dimension_field_id
        super().__init__(**kwargs)

    def _build_choices_for_dimension(self, dimension: str) -> list[tuple[str, str]]:
        units = UNITS_BY_DIMENSION.get(dimension, [])
        choices = [("", str(_("- choose a unit -")))]
        choices += [(sym, str(lbl)) for sym, lbl in units if sym]
        return choices

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> SafeString:
        final_attrs = dict(attrs or {})
        current_dim = final_attrs.pop("data-current-dimension", UnitDimension.NONE)

        self.choices = self._build_choices_for_dimension(current_dim)

        final_attrs["data-units-map"] = _UNITS_JSON
        final_attrs["data-dim-field"] = self._dim_field_id
        final_attrs["data-placeholder"] = str(_("- choose a unit -"))

        html = super().render(name, value, final_attrs, renderer)

        widget_id = final_attrs.get("id", f"id_{name}")
        script = format_html(
            """
<script>
(function() {{
  function initUnitSymbolWidget(selectEl) {{
    var dimFieldId = selectEl.getAttribute('data-dim-field');
    var unitsMap = JSON.parse(selectEl.getAttribute('data-units-map'));
    var placeholder = selectEl.getAttribute('data-placeholder');

    function repopulate(dimension, keepValue) {{
      var units = unitsMap[dimension] || [];
      var current = keepValue !== undefined ? keepValue : selectEl.value;
      selectEl.innerHTML = '';
      var blank = document.createElement('option');
      blank.value = '';
      blank.textContent = placeholder;
      selectEl.appendChild(blank);
      units.forEach(function(pair) {{
        var sym = pair[0], lbl = pair[1];
        if (!sym) return;
        var opt = document.createElement('option');
        opt.value = sym;
        opt.textContent = lbl;
        if (sym === current) opt.selected = true;
        selectEl.appendChild(opt);
      }});
    }}

    var dimField = document.getElementById(dimFieldId);
    if (!dimField) return;
    dimField.addEventListener('change', function() {{
      repopulate(dimField.value, '');
    }});
    var initialValue = selectEl.getAttribute('data-initial-value')
      || selectEl.value;
    repopulate(dimField.value, initialValue);
  }}

  function setup() {{
    var el = document.getElementById('{}');
    if (el) {{
      el.setAttribute('data-initial-value', el.value);
      initUnitSymbolWidget(el);
    }}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', setup);
  }} else {{
    setup();
  }}
}})();
</script>""",
            widget_id,
        )
        return format_html("{}{}", html, script)


# ShippingDimensionsWidget constants
_SHIPPING_ROWS: list[tuple[str, str, str, str]] = [
    ("weight", "Weight", "mass", "kilogram"),
    ("length", "Length", "length", "centimeter"),
    ("width", "Width", "length", "centimeter"),
    ("height", "Height", "length", "centimeter"),
]

_SHIPPABLE_FULFILMENT_TYPES: frozenset[str] = frozenset(
    {"shipment", "local_delivery", "store_pickup"}
)

_FULL_UNITS_JSON: str = json.dumps(
    {
        dim: [[sym, lbl] for sym, lbl in units]
        for dim, units in UNITS_BY_DIMENSION.items()
    },
    ensure_ascii=False,
)

_SHIPPABLE_TYPES_JSON: str = json.dumps(sorted(_SHIPPABLE_FULFILMENT_TYPES))


class ShippingDimensionsWidget(forms.Widget):
    """
    Compound widget for Product.other_attributes.

    Renders shipping dimension rows (weight / length / width / height) inside a
    collapsible group that appears only when a shippable fulfilment type is
    selected. Below that, a generic key-value table handles any extra attributes.
    """

    template_name = ""

    def __init__(
        self,
        fulfilment_field_id: str = "id_fulfilment_type",
        **kwargs: Any,
    ) -> None:
        self._fulfilment_field_id = fulfilment_field_id
        super().__init__(**kwargs)

    def _parse_value(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return dict(parsed) if isinstance(parsed, dict) else {}
            except json.JSONDecodeError, TypeError:
                return {}
        return {}

    def _build_unit_options(self, dimension: str, selected: str) -> SafeString:
        units = UNITS_BY_DIMENSION.get(dimension, [])
        options_html = format_html(
            "<option value=''>{}</option>",
            _("- select unit -"),
        )
        for sym, lbl in units:
            if not sym:
                continue
            if sym == selected:
                options_html = format_html(
                    "{}<option value='{}' selected>{}</option>",
                    options_html,
                    sym,
                    lbl,
                )
            else:
                options_html = format_html(
                    "{}<option value='{}'>{}</option>",
                    options_html,
                    sym,
                    lbl,
                )
        return options_html

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> SafeString:
        data = self._parse_value(value)
        widget_id = (attrs or {}).get("id", f"id_{name}")

        # Section 1: Shipping Dimensions
        dim_rows_html: SafeString = mark_safe("")
        for json_key, label, dimension, default_unit in _SHIPPING_ROWS:
            row_val = data.pop(json_key, "")
            unit_key = f"{json_key}_unit"
            row_unit = data.pop(unit_key, default_unit)
            options_html = self._build_unit_options(dimension, str(row_unit))

            dim_rows_html = format_html(
                """{}
<tr class="shipping-dim-row border-b border-base-200 dark:border-base-700"
    data-key="{}" data-unit-key="{}" data-dimension="{}">
  <td class="py-3 px-4 font-medium text-sm text-base-700
      dark:text-base-300 w-1/4">{}</td>
  <td class="py-3 px-2 w-1/3">
    <input type="number" step="any" min="0"
           id="{}_{}"
           name="{}__ship__{}"
           value="{}"
           class="{} shipping-dim-value rounded-l-default"
           placeholder="0.0"
           aria-label="{}">
  </td>
  <td class="py-3 px-2 w-1/3">
    <select id="{}_{}"
            name="{}__ship__{}_unit"
            class="{} shipping-dim-unit"
            data-dimension="{}"
            data-units-map="{}"
            aria-label="{} unit">
      {}
    </select>
  </td>
</tr>""",
                dim_rows_html,
                json_key,
                unit_key,
                dimension,
                label,
                widget_id,
                json_key,
                name,
                json_key,
                str(row_val),
                _KV_INPUT,
                label,
                widget_id,
                unit_key,
                name,
                json_key,
                _KV_SELECT,
                dimension,
                _FULL_UNITS_JSON,
                label,
                options_html,
            )

        shipping_section = format_html(
            """
<div id="{}_shipping_section" class="shipping-dims-group">
  <div class="border border-base-200 dark:border-base-700
      rounded-default overflow-hidden">
    <div class="bg-base-50 dark:bg-base-800 px-4 py-3
        border-b border-base-200 dark:border-base-700">
      <h3 class="text-sm font-semibold text-base-700
          dark:text-base-300 m-0">{}</h3>
      <p class="text-xs text-base-500 dark:text-base-400
         mt-1 m-0">{}</p>
    </div>
    <table class="w-full">
      <thead>
        <tr class="border-b border-base-200 dark:border-base-700
            bg-base-50 dark:bg-base-800">
          <th class="px-4 py-2 text-left text-xs font-medium
              text-base-500 dark:text-base-400 uppercase
              tracking-wider">{}</th>
          <th class="px-4 py-2 text-left text-xs font-medium
              text-base-500 dark:text-base-400 uppercase
              tracking-wider">{}</th>
          <th class="px-4 py-2 text-left text-xs font-medium
              text-base-500 dark:text-base-400 uppercase
              tracking-wider">{}</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-base-200
             dark:divide-base-700">
        {}
      </tbody>
    </table>
  </div>
</div>""",
            widget_id,
            _("Shipping Dimensions"),
            _(
                "Required for all shippable products. "
                "Used by the shipping app to calculate carrier rates."
            ),
            _("Property"),
            _("Value"),
            _("Unit"),
            dim_rows_html,
        )

        # Section 2: Generic extra attributes (key/value)
        remaining_pairs = [(str(k), str(v)) for k, v in data.items()]
        remaining_pairs.append(("", ""))

        kv_tbody_id = f"{widget_id}_kv_tbody"
        kv_rows_html = format_html_join(
            "",
            '<tr class="kv-row border-b border-base-200'
            ' dark:border-base-700">'
            '<td class="py-2 pl-2 w-1/2">'
            '<input type="text" name="{}" value="{}" id="{}"'
            ' class="{} kv-key rounded-l-default" placeholder="{}">'
            "</td>"
            '<td class="py-2 pl-2 w-1/2">'
            '<input type="text" name="{}" value="{}" id="{}"'
            ' class="{} kv-val" placeholder="{}">'
            "</td>"
            '<td class="py-2 w-12">'
            '<a href="#" class="deletelink kv-remove-btn cursor-pointer flex'
            " h-[38px] w-[38px] items-center justify-center rounded-default"
            " select-none transition-colors hover:bg-base-50"
            ' dark:hover:bg-base-800"'
            ' title="Remove">'
            "{}"
            "</a>"
            "</td>"
            "</tr>",
            (
                (
                    f"{name}__kv__key__{idx}",
                    k,
                    f"{widget_id}_kv_key_{idx}",
                    _KV_INPUT,
                    _("Key"),
                    f"{name}__kv__val__{idx}",
                    v,
                    f"{widget_id}_kv_val_{idx}",
                    _KV_INPUT,
                    _("Value"),
                    _DELETE_ICON,
                )
                for idx, (k, v) in enumerate(remaining_pairs)
            ),
        )

        kv_section = format_html(
            """
<div id="{}_kv_section" class="extra-attrs-group mt-6">
  <div class="border border-base-200 dark:border-base-700
      rounded-default overflow-hidden">
    <div class="bg-base-50 dark:bg-base-800 px-4 py-3
        border-b border-base-200 dark:border-base-700">
      <h3 class="text-sm font-semibold text-base-700
          dark:text-base-300 m-0">{}</h3>
      <p class="text-xs text-base-500 dark:text-base-400
         mt-1 m-0">{}</p>
    </div>
    <table class="w-full">
      <thead>
        <tr class="border-b border-base-200 dark:border-base-700
            bg-base-50 dark:bg-base-800">
          <th class="px-4 py-2 text-left text-xs font-medium
              text-base-500 dark:text-base-400 uppercase
              tracking-wider">{}</th>
          <th class="px-4 py-2 text-left text-xs font-medium
              text-base-500 dark:text-base-400 uppercase
              tracking-wider">{}</th>
          <th class="px-4 py-2 w-12"></th>
        </tr>
      </thead>
      <tbody id="{}" class="divide-y divide-base-200
             dark:divide-base-700">
        {}
      </tbody>
    </table>
  </div>
  <div class="mt-3">
    <a href="#" class="kv-add-btn inline-flex items-center
       gap-2 text-sm font-medium text-primary-600
       hover:text-primary-700 dark:text-primary-400
       dark:hover:text-primary-300 transition-colors"
       data-container="{}"
       data-name="{}"
       data-next="{}"
       data-widget-id="{}">
      {} {}
    </a>
  </div>
</div>""",
            widget_id,
            _("Extra Attributes"),
            _(
                "Arbitrary key/value pairs for attributes not covered "
                "by the structured system above."
            ),
            _("Key"),
            _("Value"),
            kv_tbody_id,
            kv_rows_html,
            kv_tbody_id,
            name,
            len(remaining_pairs),
            widget_id,
            _ADD_ICON,
            _("Add another"),
        )

        # JS controller
        script = format_html(
            """
<script>
(function() {{
  var SHIPPABLE = {};
  var shippingSectionId = '{}_shipping_section';
  var fulfilmentFieldId = '{}';

  function setShippingVisibility(val) {{
    var sec = document.getElementById(shippingSectionId);
    if (!sec) return;
    if (SHIPPABLE.indexOf(val) !== -1) {{
      sec.style.display = '';
      sec.style.opacity = '0';
      sec.style.transform = 'translateY(-10px)';
      requestAnimationFrame(function() {{
        sec.style.transition = 'opacity 0.3s, transform 0.3s';
        sec.style.opacity = '1';
        sec.style.transform = 'translateY(0)';
      }});
    }} else {{
      sec.style.display = 'none';
    }}
  }}

  document.addEventListener('click', function(e) {{
    var addBtn = e.target.closest('.kv-add-btn');
    if (!addBtn) return;
    e.preventDefault();
    var tbodyId = addBtn.getAttribute('data-container');
    var baseName = addBtn.getAttribute('data-name');
    var next = parseInt(addBtn.getAttribute('data-next'), 10);
    addBtn.setAttribute('data-next', next + 1);
    var tbody = document.getElementById(tbodyId);
    var tr = document.createElement('tr');
    tr.className = 'kv-row border-b border-base-200 dark:border-base-700';
    tr.style.opacity = '0';
    tr.style.transform = 'translateY(-5px)';
    tr.innerHTML =
      '<td class="py-2 pl-2 w-1/2"><input type="text" name="'
      + baseName + '__kv__key__' + next + '" class="{} kv-key'
      + ' rounded-l-default" placeholder="{}"></td>'
      + '<td class="py-2 pl-2 w-1/2"><input type="text" name="'
      + baseName + '__kv__val__' + next + '" class="{} kv-val'
      + '" placeholder="{}"></td>'
      + '<td class="py-2 w-12"><a href="#" class="deletelink'
      + ' kv-remove-btn cursor-pointer flex h-[38px] w-[38px]'
      + ' items-center justify-center rounded-default select-none'
      + ' transition-colors hover:bg-base-50 dark:hover:bg-base-800"'
      + ' title="Remove">'
      + 'TRASH_ICON_PLACEHOLDER'
      + '</a></td>';
    tbody.appendChild(tr);
    requestAnimationFrame(function() {{
      tr.style.transition = 'opacity 0.2s, transform 0.2s';
      tr.style.opacity = '1';
      tr.style.transform = 'translateY(0)';
    }});
  }});

  document.addEventListener('click', function(e) {{
    var btn = e.target.closest('.kv-remove-btn');
    if (!btn) return;
    e.preventDefault();
    var row = btn.closest('.kv-row');
    if (row) {{
      row.style.opacity = '0';
      row.style.transform = 'translateX(-10px)';
      row.style.transition = 'opacity 0.2s, transform 0.2s';
      setTimeout(function() {{ row.remove(); }}, 200);
    }}
  }});

  function init() {{
    var fulfilmentField = document.getElementById(fulfilmentFieldId);
    if (fulfilmentField) {{
      setShippingVisibility(fulfilmentField.value);
      fulfilmentField.addEventListener('change', function() {{
        setShippingVisibility(this.value);
      }});
    }}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', init);
  }} else {{
    init();
  }}
}})();
</script>""",
            _SHIPPABLE_TYPES_JSON,
            widget_id,
            self._fulfilment_field_id,
            _KV_INPUT,
            _("Key"),
            _KV_INPUT,
            _("Value"),
        )
        # Replace placeholder with actual icon (avoids format_html escaping)
        icon_replacement = str(_DELETE_ICON)
        script = mark_safe(  # noqa: S308 - controlled HTML content
            str(script).replace("TRASH_ICON_PLACEHOLDER", icon_replacement)
        )

        return format_html(
            "<div class='shipping-attrs-widget space-y-4'>{}{}{}</div>",
            shipping_section,
            kv_section,
            script,
        )

    def value_from_datadict(
        self,
        data: Any,
        files: Any,
        name: str,
    ) -> str:
        result: dict[str, Any] = {}

        ship_prefix_key = f"{name}__ship__"
        for key, _label, _dim, _default_unit in _SHIPPING_ROWS:
            val_field = f"{ship_prefix_key}{key}"
            unit_field = f"{ship_prefix_key}{key}_unit"
            raw_val = data.get(val_field, "").strip()
            raw_unit = data.get(unit_field, "").strip()
            if raw_val:
                try:
                    result[key] = float(raw_val)
                except ValueError:
                    result[key] = raw_val
            if raw_unit:
                result[f"{key}_unit"] = raw_unit

        kv_prefix_key = f"{name}__kv__key__"
        kv_prefix_val = f"{name}__kv__val__"
        indices: list[int] = []
        for field_name in data:
            if field_name.startswith(kv_prefix_key):
                with contextlib.suppress(ValueError):
                    indices.append(int(field_name[len(kv_prefix_key) :]))
        for idx in sorted(indices):
            key = data.get(f"{kv_prefix_key}{idx}", "").strip()
            val = data.get(f"{kv_prefix_val}{idx}", "").strip()
            if key:
                result[key] = val

        return json.dumps(result)

    def value_omitted_from_data(
        self,
        data: Any,
        files: Any,
        name: str,
    ) -> bool:
        ship_prefix = f"{name}__ship__"
        kv_prefix = f"{name}__kv__key__"
        return not any(k.startswith((ship_prefix, kv_prefix)) for k in data)


class ShippingAttributesField(forms.Field):
    """
    Form field that pairs with ShippingDimensionsWidget.
    """

    widget = ShippingDimensionsWidget

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", _("Attributes & Dimensions"))
        kwargs.setdefault(
            "help_text",
            _(
                "Shipping dimensions are required for physical/shippable products. "
                "Use Extra Attributes for any additional product properties."
            ),
        )
        super().__init__(**kwargs)

    def prepare_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError, TypeError:
                return {}
        return {}

    def to_python(self, value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError, TypeError:
                pass
        return {}

    def validate(self, value: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Attribute value widget - renders the correct Unfold-styled input for the
# selected attribute definition and embeds JS that swaps the input when the
# user picks a different definition via AJAX.
# ---------------------------------------------------------------------------

_INPUT_TYPE_MAP: dict[str, str] = {
    AttributeValueType.INTEGER: "number",
    AttributeValueType.BIG_INTEGER: "number",
    AttributeValueType.DECIMAL: "number",
    AttributeValueType.FLOAT: "number",
    AttributeValueType.EMAIL: "email",
    AttributeValueType.URL: "url",
    AttributeValueType.DATE: "date",
    AttributeValueType.TIME: "time",
    AttributeValueType.DATETIME: "datetime-local",
}

_INPUT_CLASSES = " ".join(INPUT_CLASSES)
_SELECT_CLASSES = " ".join(SELECT_CLASSES)
_TEXTAREA_CLASSES = " ".join(TEXTAREA_CLASSES)
_COLOR_CLASSES = " ".join(COLOR_CLASSES)
_CHECKBOX_CLASSES = " ".join(CHECKBOX_CLASSES)


def _esc(s: Any) -> str:
    """HTML-escape a value for safe insertion."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_select(
    name: str, choices: list[tuple[str, str]], current: str
) -> SafeString:
    opts = '<option value="">---------</option>'
    for val, label in choices:
        sel = " selected" if str(val) == str(current) else ""
        opts += f'<option value="{_esc(val)}"{sel}>{_esc(label)}</option>'
    return mark_safe(  # noqa: S308
        f'<div class="relative max-w-2xl w-full">'
        f'<select name="{name}" class="{_SELECT_CLASSES}">{opts}</select>'
        f'<span class="material-symbols-outlined absolute pointer-events-none '
        f"mr-[12px] right-0 text-base-400 top-1/2 hover:text-base-700 "
        f'dark:text-base-500 dark:hover:text-base-200 -translate-y-1/2">'
        f"expand_more</span></div>"
    )


def _render_checkboxes(
    name: str, choices: list[tuple[str, str]], current: str
) -> SafeString:
    vals = [v.strip() for v in str(current).split(",") if v.strip()] if current else []
    html = '<div class="flex flex-col gap-2">'
    for i, (val, label) in enumerate(choices):
        checked = " checked" if val in vals else ""
        cid = f"{name.replace('-', '_')}_{i}"
        html += (
            f'<label for="{cid}" class="flex items-center gap-2 cursor-pointer">'
            f'<input type="checkbox" id="{cid}" name="{name}" '
            f'value="{_esc(val)}"{checked} class="{_CHECKBOX_CLASSES}">'
            f'<span class="truncate text-sm">{_esc(label)}</span></label>'
        )
    html += "</div>"
    return mark_safe(html)  # noqa: S308


def _render_input(name: str, value_type: str, current: str) -> SafeString:
    input_type = _INPUT_TYPE_MAP.get(value_type, "text")
    return mark_safe(  # noqa: S308
        f'<div class="max-w-2xl relative w-full">'
        f'<input type="{input_type}" name="{name}" '
        f'value="{_esc(current)}" class="{_INPUT_CLASSES}"></div>'
    )


def _render_textarea(name: str, current: str) -> SafeString:
    return mark_safe(  # noqa: S308
        f'<textarea name="{name}" class="{_TEXTAREA_CLASSES}" '
        f'rows="4">{_esc(current)}</textarea>'
    )


def _render_color(name: str, current: str) -> SafeString:
    return mark_safe(  # noqa: S308
        f'<input type="color" name="{name}" '
        f'value="{_esc(current or "#000000")}" class="{_COLOR_CLASSES}">'
    )


def _render_value(
    name: str,
    value_type: str,
    current: str,
    options: list[tuple[str, str]] | None = None,
) -> SafeString:
    """Render the correct input for a given value_type."""
    if value_type == AttributeValueType.BOOLEAN:
        return _render_select(
            name, [("true", str(_("Yes"))), ("false", str(_("No")))], current
        )
    if value_type == AttributeValueType.SINGLE_SELECT:
        return _render_select(name, options or [], current)
    if value_type == AttributeValueType.MULTI_SELECT:
        return _render_checkboxes(name, options or [], current)
    if value_type == AttributeValueType.LONG_TEXT:
        return _render_textarea(name, current)
    if value_type == AttributeValueType.COLOR:
        return _render_color(name, current)
    return _render_input(name, value_type, current)


class AttributeValueWidget(forms.Widget):
    """Renders the value field for an attribute-value inline.

    Accepts ``definition`` (an ``AttributeDefinition`` instance or ``None``)
    via ``__init__``.  Renders the matching Unfold-styled input and loads JS
    that swaps the input when the user picks a different definition.
    """

    template_name = ""

    class Media:
        js = ("catalogue/js/attribute-value-widget.js",)
        css: dict[str, tuple[str, ...]] = {}

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        definition: AttributeDefinition | None = None,
    ) -> None:
        super().__init__(attrs=attrs)
        self.definition = definition

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> SafeString:
        current = str(value) if value is not None else ""
        defn = self.definition

        if defn is not None:
            value_type = defn.value_type
            options = (
                [
                    (opt.value, opt.label)
                    for opt in defn.options.filter(is_active=True).order_by(
                        "display_order"
                    )
                ]
                if hasattr(defn, "options")
                else []
            )
            return _render_value(name, value_type, current, options)

        return _render_input(name, AttributeValueType.TEXT, current)
