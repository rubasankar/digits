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

from apps.catalogue.enums import UNITS_BY_DIMENSION
from apps.catalogue.enums import UnitDimension

if TYPE_CHECKING:
    from django.utils.safestring import SafeString


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
                except (json.JSONDecodeError, TypeError):  # fmt: skip
                    decoded = {}
            else:
                decoded = value if isinstance(value, dict) else {}
            pairs = [(str(k), str(v)) for k, v in decoded.items()]

        pairs.append(("", ""))

        widget_id = (attrs or {}).get("id", f"id_{name}")
        container_id = f"{widget_id}_kv_container"

        row_template = (
            '<tr class="kv-row">'
            '<td><input type="text" name="{}" value="{}" id="{}"'
            ' class="vTextField kv-key" placeholder="{}"></td>'
            '<td><input type="text" name="{}" value="{}" id="{}"'
            ' class="vTextField kv-val" placeholder="{}"></td>'
            '<td><a href="#" class="deletelink kv-remove-btn" title="{}"></a></td>'
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
                    _("Key"),
                    f"{name}__val__{idx}",
                    v,
                    f"{widget_id}_val_{idx}",
                    _("Value"),
                    _("Remove row"),
                )
                for idx, (k, v) in enumerate(pairs)
            ),
        )

        table_html = format_html(
            '<div id="{container_id}" class="js-inline-admin-formset inline-group">'
            '<div class="tabular inline-related">'
            '<fieldset class="module">'
            "<table>"
            "<thead>"
            "<tr>"
            '<th class="column-key">{th_key}</th>'
            '<th class="column-value">{th_val}</th>'
            '<th class="column-remove"></th>'
            "</tr>"
            "</thead>"
            '<tbody id="{tbody_id}">{rows}</tbody>'
            "</table>"
            "</fieldset>"
            '<div class="add-row">'
            '<a href="#" class="addlink kv-add-btn" data-container="{tbody_id}"'
            ' data-name="{name}" data-next="{next_idx}"'
            ' data-widget-id="{widget_id}">{add_label}</a>'
            "</div>"
            "</div>"
            "</div>",
            container_id=container_id,
            th_key=_("Key"),
            th_val=_("Value"),
            tbody_id=f"{widget_id}_kv_tbody",
            rows=rows_html,
            name=name,
            next_idx=len(pairs),
            widget_id=widget_id,
            add_label=_("Add another"),
        )

        script = format_html(
            """
<script>
(function() {{
  function kvInit() {{
    // Remove-row buttons
    document.addEventListener('click', function(e) {{
      var btn = e.target.closest('.kv-remove-btn');
      if (!btn) return;
      e.preventDefault();
      var row = btn.closest('.kv-row');
      if (row) row.remove();
    }});

    // Add-row buttons
    document.addEventListener('click', function(e) {{
      var btn = e.target.closest('.kv-add-btn');
      if (!btn) return;
      e.preventDefault();
      var tbodyId = btn.getAttribute('data-container');
      var baseName = btn.getAttribute('data-name');
      var widgetId = btn.getAttribute('data-widget-id');
      var next = parseInt(btn.getAttribute('data-next'), 10);
      btn.setAttribute('data-next', next + 1);

      var tbody = document.getElementById(tbodyId);
      var tr = document.createElement('tr');
      tr.className = 'kv-row';
      tr.innerHTML =
        '<td><input type="text" name="' + baseName + '__key__' + next + '"'
        + ' class="vTextField kv-key" placeholder="{kph}"></td>'
        + '<td><input type="text" name="' + baseName + '__val__' + next + '"'
        + ' class="vTextField kv-val" placeholder="{vph}"></td>'
        + '<td><a href="#" class="deletelink kv-remove-btn" title="{del_title}">'
        + '</a></td>';
      tbody.appendChild(tr);
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', kvInit);
  }} else {{
    kvInit();
  }}
}})();
</script>""",
            kph=_("Key"),
            vph=_("Value"),
            del_title=_("Remove row"),
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
            if key:  # drop rows with empty key
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
            except (json.JSONDecodeError, TypeError):  # fmt: skip
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
            except (json.JSONDecodeError, TypeError):  # fmt: skip
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


class UnitSymbolWidget(forms.Select):
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
    var unitsMap   = JSON.parse(selectEl.getAttribute('data-units-map'));
    var placeholder = selectEl.getAttribute('data-placeholder');

    function repopulate(dimension, keepValue) {{
      var units = unitsMap[dimension] || [];
      var current = keepValue !== undefined ? keepValue : selectEl.value;
      selectEl.innerHTML = '';

      // Blank sentinel
      var blank = document.createElement('option');
      blank.value = '';
      blank.textContent = placeholder;
      selectEl.appendChild(blank);

      units.forEach(function(pair) {{
        var sym = pair[0], lbl = pair[1];
        if (!sym) return;  // skip empty sentinel from NONE group
        var opt = document.createElement('option');
        opt.value = sym;
        opt.textContent = lbl;
        if (sym === current) opt.selected = true;
        selectEl.appendChild(opt);
      }});
    }}

    var dimField = document.getElementById(dimFieldId);
    if (!dimField) return;

    // Re-populate whenever the dimension changes
    dimField.addEventListener('change', function() {{
      repopulate(dimField.value, '');
    }});

    // On first load, ensure the currently-saved value is selected
    var initialValue = selectEl.getAttribute('data-initial-value')
      || selectEl.value;
    repopulate(dimField.value, initialValue);
  }}

  function setup() {{
    var el = document.getElementById('{widget_id}');
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
            widget_id=widget_id,
        )
        return format_html("{}{}", html, script)


# ShippingDimensionsWidget
#
# Renders a two-section widget for Product.other_attributes:
#
#   SECTION 1 - "Shipping Dimensions" (shown only for shippable fulfilment types)
#     Four fixed rows: weight, length, width, height.
#     Each row: Label | numeric value input | unit <select> (filtered by dimension)
#
#   SECTION 2 - "Extra Attributes" (always visible)
#     The generic key/value table from KeyValueWidget for any remaining attributes.
#
# Both sections write into the same JSONField. The JS layer reads the current
# value of the "fulfilment_type" select and hides/shows the shipping section.
#
# Shippable fulfilment types (must match FulfilmentType enum values):
#   shipment | local_delivery | store_pickup


# Dimension definitions for the four shipping rows.
# Each entry: (json_key, display_label, unit_dimension_value, default_unit_symbol)
_SHIPPING_ROWS: list[tuple[str, str, str, str]] = [
    ("weight", "Weight", "mass", "kilogram"),
    ("length", "Length", "length", "centimeter"),
    ("width", "Width", "length", "centimeter"),
    ("height", "Height", "length", "centimeter"),
]

# The set of FulfilmentType values that require shipping dimensions.
_SHIPPABLE_FULFILMENT_TYPES: frozenset[str] = frozenset(
    {"shipment", "local_delivery", "store_pickup"}
)

# Pre-serialise the full UNITS_BY_DIMENSION map once (reused across renders).
_FULL_UNITS_JSON: str = json.dumps(
    {
        dim: [[sym, lbl] for sym, lbl in units]
        for dim, units in UNITS_BY_DIMENSION.items()
    },
    ensure_ascii=False,
)

# Pre-serialise the set of shippable types for the JS layer.
_SHIPPABLE_TYPES_JSON: str = json.dumps(sorted(_SHIPPABLE_FULFILMENT_TYPES))


class ShippingDimensionsWidget(forms.Widget):
    """
    Compound widget for Product.other_attributes.

    Renders shipping dimension rows (weight / length / width / height) inside a
    collapsible group that appears only when a shippable fulfilment type is
    selected.  Below that, a generic key-value table handles any extra attributes
    the staff member wants to record.

    The fulfilment_type select is located by the CSS id that Django admin assigns
    to the field: ``id_fulfilment_type``.  If your form prefixes differ, pass
    ``fulfilment_field_id`` to the constructor.
    """

    template_name = ""

    def __init__(
        self,
        fulfilment_field_id: str = "id_fulfilment_type",
        **kwargs: Any,
    ) -> None:
        self._fulfilment_field_id = fulfilment_field_id
        super().__init__(**kwargs)

    # Helpers

    def _parse_value(self, value: Any) -> dict[str, Any]:
        """Coerce the stored value (string or dict) to a plain dict."""
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
        """Render <option> elements for a unit <select>."""
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

    # Render

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
        dim_rows_html: SafeString = mark_safe("")  # initial seed, no user data
        for json_key, label, dimension, default_unit in _SHIPPING_ROWS:
            row_val = data.pop(json_key, "")
            unit_key = f"{json_key}_unit"
            row_unit = data.pop(unit_key, default_unit)

            options_html = self._build_unit_options(dimension, str(row_unit))

            dim_rows_html = format_html(
                """{}
<tr class="shipping-dim-row" data-key="{key}" data-unit-key="{unit_key}"
    data-dimension="{dim}">
  <th class="shipping-dim-label">{label}</th>
  <td>
    <input type="number" step="any" min="0"
           id="{widget_id}_{key}"
           name="{name}__ship__{key}"
           value="{val}"
           class="vTextField shipping-dim-value"
           placeholder="0.0"
           aria-label="{label}">
  </td>
  <td>
    <select id="{widget_id}_{unit_key}"
            name="{name}__ship__{unit_key}"
            class="shipping-dim-unit"
            data-dimension="{dim}"
            data-units-map="{units_map_attr}"
            aria-label="{label} unit">
      {opts}
    </select>
  </td>
</tr>""",
                dim_rows_html,
                key=json_key,
                unit_key=unit_key,
                dim=dimension,
                label=label,
                widget_id=widget_id,
                name=name,
                val=str(row_val),
                units_map_attr=_FULL_UNITS_JSON,
                opts=options_html,
            )

        shipping_section = format_html(
            """
<div id="{wid}_shipping_section" class="shipping-dims-group module aligned">
  <h2 class="shipping-dims-title">{title}</h2>
  <p class="help">{help_text}</p>
  <table class="shipping-dims-table">
    <thead>
      <tr>
        <th>{th_property}</th>
        <th>{th_value}</th>
        <th>{th_unit}</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>""",
            wid=widget_id,
            title=_("Shipping Dimensions"),
            help_text=_(
                "Required for all shippable products. "
                "Used by the shipping app to calculate carrier rates."
            ),
            th_property=_("Property"),
            th_value=_("Value"),
            th_unit=_("Unit"),
            rows=dim_rows_html,
        )

        # Section 2: Generic extra attributes (key/value)
        # `data` at this point contains only the keys NOT consumed by the
        # shipping rows above.
        remaining_pairs = [(str(k), str(v)) for k, v in data.items()]
        remaining_pairs.append(("", ""))  # blank sentinel row for adding new

        kv_tbody_id = f"{widget_id}_kv_tbody"
        kv_rows_html = format_html_join(
            "",
            '<tr class="kv-row">'
            '<td><input type="text" name="{0}" value="{1}" id="{2}"'
            ' class="vTextField kv-key" placeholder="{3}"></td>'
            '<td><input type="text" name="{4}" value="{5}" id="{6}"'
            ' class="vTextField kv-val" placeholder="{7}"></td>'
            '<td><a href="#" class="deletelink kv-remove-btn" title="{8}"></a></td>'
            "</tr>",
            (
                (
                    f"{name}__kv__key__{idx}",
                    k,
                    f"{widget_id}_kv_key_{idx}",
                    _("Key"),
                    f"{name}__kv__val__{idx}",
                    v,
                    f"{widget_id}_kv_val_{idx}",
                    _("Value"),
                    _("Remove"),
                )
                for idx, (k, v) in enumerate(remaining_pairs)
            ),
        )

        kv_section = format_html(
            """
<div id="{wid}_kv_section" class="extra-attrs-group module aligned">
  <h2 class="extra-attrs-title">{title}</h2>
  <p class="help">{help_text}</p>
  <div class="tabular inline-related">
    <fieldset class="module">
      <table>
        <thead>
          <tr>
            <th>{th_key}</th>
            <th>{th_val}</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="{tbody_id}">
          {rows}
        </tbody>
      </table>
    </fieldset>
    <div class="add-row">
      <a href="#" class="addlink kv-add-btn"
         data-container="{tbody_id}"
         data-name="{name}"
         data-next="{next_idx}"
         data-widget-id="{wid}">{add_label}</a>
    </div>
  </div>
</div>""",
            wid=widget_id,
            title=_("Extra Attributes"),
            help_text=_(
                "Arbitrary key/value pairs for attributes not covered "
                "by the structured system above."
            ),
            th_key=_("Key"),
            th_val=_("Value"),
            tbody_id=kv_tbody_id,
            rows=kv_rows_html,
            name=name,
            next_idx=len(remaining_pairs),
            add_label=_("Add another"),
        )

        # JS controller
        script = format_html(
            """
<script>
(function() {{
  var SHIPPABLE = {shippable_json};
  var shippingSectionId = '{wid}_shipping_section';
  var fulfilmentFieldId = '{fulfilment_field_id}';

  function setShippingVisibility(val) {{
    var sec = document.getElementById(shippingSectionId);
    if (!sec) return;
    if (SHIPPABLE.indexOf(val) !== -1) {{
      sec.style.display = '';
    }} else {{
      sec.style.display = 'none';
    }}
  }}

  // KV add-row handler (same as KeyValueWidget)
  document.addEventListener('click', function(e) {{
    var addBtn = e.target.closest('.kv-add-btn');
    if (!addBtn) return;
    e.preventDefault();
    var tbodyId = addBtn.getAttribute('data-container');
    var baseName = addBtn.getAttribute('data-name');
    var widgetId = addBtn.getAttribute('data-widget-id');
    var next = parseInt(addBtn.getAttribute('data-next'), 10);
    addBtn.setAttribute('data-next', next + 1);
    var tbody = document.getElementById(tbodyId);
    var tr = document.createElement('tr');
    tr.className = 'kv-row';
    tr.innerHTML =
      '<td><input type="text" name="' + baseName + '__kv__key__' + next + '"'
      + ' class="vTextField kv-key" placeholder="{kph}"></td>'
      + '<td><input type="text" name="' + baseName + '__kv__val__' + next + '"'
      + ' class="vTextField kv-val" placeholder="{vph}"></td>'
      + '<td><a href="#" class="deletelink kv-remove-btn" title="{del_t}"></a></td>';
    tbody.appendChild(tr);
  }});

  // KV remove-row handler
  document.addEventListener('click', function(e) {{
    var btn = e.target.closest('.kv-remove-btn');
    if (!btn) return;
    e.preventDefault();
    var row = btn.closest('.kv-row');
    if (row) row.remove();
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
            shippable_json=_SHIPPABLE_TYPES_JSON,
            wid=widget_id,
            fulfilment_field_id=self._fulfilment_field_id,
            kph=_("Key"),
            vph=_("Value"),
            del_t=_("Remove"),
        )

        return format_html(
            "<div class='shipping-attrs-widget'>{}{}{}</div>",
            shipping_section,
            kv_section,
            script,
        )

    # Data extraction (POST)

    def value_from_datadict(
        self,
        data: Any,
        files: Any,
        name: str,
    ) -> str:
        result: dict[str, Any] = {}

        # Extract shipping dimension rows
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

        # Extract generic key-value pairs
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

    Accepts a dict (from model) or the serialised JSON string produced by
    ShippingDimensionsWidget.value_from_datadict() and returns a plain dict
    ready to be written back to the JSONField.
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
        # Deep validation is handled by Product.clean() on the model side.
        pass
