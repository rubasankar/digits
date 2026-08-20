from __future__ import annotations

import pytest

from apps.catalogue.enums import UnitDimension
from apps.catalogue.models.attribute import AttributeDefinition
from apps.catalogue.service.attribute import AttributeService

pytestmark = pytest.mark.django_db


def test_create_definition_persists_unit_symbol() -> None:
    defn = AttributeService.create_definition(
        name="weight",
        label="Weight",
        unit_symbol="percent",
    )

    assert isinstance(defn, AttributeDefinition)
    assert defn.unit_symbol == "percent"


def test_update_definition_updates_unit_symbol() -> None:
    defn = AttributeService.create_definition(
        name="length",
        label="Length",
        unit_symbol="percent",
    )

    updated = AttributeService.update_definition(
        defn,
        unit_symbol="ppm",
    )

    assert updated.unit_symbol == "ppm"
    assert updated.unit_dimension == UnitDimension.NONE
