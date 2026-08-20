from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.utils.html import format_html
from django.utils.html import format_html_join
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
