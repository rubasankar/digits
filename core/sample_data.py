from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from dataclasses import field
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.apps import apps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.utils.text import slugify
from treebeard.mp_tree import MP_Node

from apps.catalogue.service.category import CategoryService

if TYPE_CHECKING:
    from django.db import models
    from django.db.models.fields.files import FieldFile


def get_sample_data_root() -> Path:
    configured = getattr(settings, "SAMPLE_DATA_DIR", None)
    if configured:
        return Path(configured)
    return Path(settings.BASE_DIR) / "fixtures" / "sample_data"


def normalize_model_key(value: str) -> str:
    return slugify(value.replace(".", " ").replace("_", " ").strip())


@dataclass(frozen=True, slots=True)
class SeedSpec:
    label: str
    app_label: str
    model_name: str
    fixture_file: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def django_label(self) -> str:
        return f"{self.app_label}.{self.model_name}"


def _build_seed_specs() -> list[SeedSpec]:
    specs = [
        # --- pricing (no FK deps) ---
        SeedSpec(
            label="currency",
            app_label="pricing",
            model_name="Currency",
            fixture_file="pricing/currency.json",
            aliases=("currencies", "pricing currency"),
        ),
        SeedSpec(
            label="tax class",
            app_label="pricing",
            model_name="TaxClass",
            fixture_file="pricing/tax_class.json",
            aliases=("tax classes", "pricing tax class"),
        ),
        SeedSpec(
            label="tax rate",
            app_label="pricing",
            model_name="TaxRate",
            fixture_file="pricing/tax_rate.json",
            aliases=("tax rates",),
        ),
        # --- payments ---
        SeedSpec(
            label="payment method",
            app_label="payments",
            model_name="PaymentMethod",
            fixture_file="payments/payment_method.json",
            aliases=("payment methods",),
        ),
        SeedSpec(
            label="refund reason",
            app_label="payments",
            model_name="RefundReason",
            fixture_file="payments/refund_reason.json",
            aliases=("refund reasons",),
        ),
        # --- staff ---
        SeedSpec(
            label="staff department",
            app_label="staff",
            model_name="StaffDepartment",
            fixture_file="staff/staff_department.json",
            aliases=("staff departments",),
        ),
        # --- accounts (must precede staff profile and customer profile) ---
        SeedSpec(
            label="user account",
            app_label="accounts",
            model_name="UserAccount",
            fixture_file="accounts/user_account.json",
            aliases=("user accounts", "users"),
        ),
        # --- staff profiles (depend on user accounts + departments) ---
        SeedSpec(
            label="staff profile",
            app_label="staff",
            model_name="StaffProfile",
            fixture_file="staff/staff_profile.json",
            aliases=("staff profiles",),
        ),
        # --- shipping ---
        SeedSpec(
            label="carrier account",
            app_label="shipping",
            model_name="CarrierAccount",
            fixture_file="shipping/carrier_account.json",
            aliases=("carrier accounts",),
        ),
        SeedSpec(
            label="shipping method",
            app_label="shipping",
            model_name="ShippingMethod",
            fixture_file="shipping/shipping_method.json",
            aliases=("shipping methods",),
        ),
        # --- catalogue: attribute definitions + options must come before products ---
        SeedSpec(
            label="attribute definition",
            app_label="catalogue",
            model_name="AttributeDefinition",
            fixture_file="catalogue/attribute_definition.json",
            aliases=("attribute definitions", "attributes"),
        ),
        SeedSpec(
            label="attribute option",
            app_label="catalogue",
            model_name="AttributeOption",
            fixture_file="catalogue/attribute_option.json",
            aliases=("attribute options",),
        ),
        SeedSpec(
            label="product category",
            app_label="catalogue",
            model_name="ProductCategory",
            fixture_file="catalogue/product_category.json",
            aliases=("product categories",),
        ),
        # attribute assignments depend on both categories and definitions
        SeedSpec(
            label="attribute assignment",
            app_label="catalogue",
            model_name="AttributeAssignment",
            fixture_file="catalogue/attribute_assignment.json",
            aliases=("attribute assignments",),
        ),
        SeedSpec(
            label="product brand",
            app_label="catalogue",
            model_name="ProductBrand",
            fixture_file="catalogue/product_brand.json",
            aliases=("product brands",),
        ),
        SeedSpec(
            label="product",
            app_label="catalogue",
            model_name="Product",
            fixture_file="catalogue/product.json",
            aliases=("products",),
        ),
        SeedSpec(
            label="product variant",
            app_label="catalogue",
            model_name="ProductVariant",
            fixture_file="catalogue/product_variant.json",
            aliases=("product variants", "variants"),
        ),
        # attribute values depend on products, variants, and definitions
        SeedSpec(
            label="product attribute value",
            app_label="catalogue",
            model_name="ProductAttributeValue",
            fixture_file="catalogue/product_attribute_value.json",
            aliases=("product attribute values",),
        ),
        SeedSpec(
            label="variant attribute value",
            app_label="catalogue",
            model_name="VariantAttributeValue",
            fixture_file="catalogue/variant_attribute_value.json",
            aliases=("variant attribute values",),
        ),
        # --- pricing (depends on variants + tax classes) ---
        SeedSpec(
            label="pricing",
            app_label="pricing",
            model_name="Pricing",
            fixture_file="pricing/pricing.json",
            aliases=("prices",),
        ),
        # --- inventory (depends on staff profiles for contact_person) ---
        SeedSpec(
            label="warehouse",
            app_label="inventory",
            model_name="Warehouse",
            fixture_file="inventory/warehouse.json",
            aliases=("warehouses",),
        ),
        SeedSpec(
            label="stock",
            app_label="inventory",
            model_name="Stock",
            fixture_file="inventory/stock.json",
            aliases=("stock levels",),
        ),
        # --- promotions (depend on catalogue) ---
        SeedSpec(
            label="campaign",
            app_label="promotions",
            model_name="Campaign",
            fixture_file="promotions/campaign.json",
            aliases=("campaigns",),
        ),
        SeedSpec(
            label="discount",
            app_label="promotions",
            model_name="Discount",
            fixture_file="promotions/discount.json",
            aliases=("discounts",),
        ),
        SeedSpec(
            label="coupon",
            app_label="promotions",
            model_name="Coupon",
            fixture_file="promotions/coupon.json",
            aliases=("coupons",),
        ),
        # --- customers (depend on user accounts) ---
        SeedSpec(
            label="customer profile",
            app_label="customers",
            model_name="CustomerProfile",
            fixture_file="customers/customer_profile.json",
            aliases=("customer profiles", "customers"),
        ),
        SeedSpec(
            label="customer address",
            app_label="customers",
            model_name="CustomerAddress",
            fixture_file="customers/customer_address.json",
            aliases=("customer addresses",),
        ),
    ]

    if find_spec("waffle") is not None:
        specs.append(
            SeedSpec(
                label="review auto publish switch",
                app_label="waffle",
                model_name="Switch",
                fixture_file="waffle/review_auto_publish_switch.json",
                aliases=("reviews auto publish switch",),
            )
        )

    return specs


SAMPLE_DATA_SPECS = tuple(_build_seed_specs())


def iter_sample_data_choices() -> list[str]:
    return sorted(
        {spec.label for spec in SAMPLE_DATA_SPECS}
        | {alias for spec in SAMPLE_DATA_SPECS for alias in spec.aliases}
    )


def build_sample_data_index() -> dict[str, SeedSpec]:
    index: dict[str, SeedSpec] = {}
    for spec in SAMPLE_DATA_SPECS:
        index[normalize_model_key(spec.label)] = spec
        index[normalize_model_key(spec.django_label)] = spec
        for alias in spec.aliases:
            index[normalize_model_key(alias)] = spec
    return index


def resolve_seed_specs(selected: list[str] | None) -> list[SeedSpec]:
    index = build_sample_data_index()
    if not selected:
        return list(SAMPLE_DATA_SPECS)

    requested_keys: set[str] = set()
    for raw_value in selected:
        for chunk in raw_value.split(","):
            key = normalize_model_key(chunk)
            spec = index.get(key)
            if spec is None:
                msg = (
                    f"Unknown sample data model '{chunk}'. "
                    f"Available choices: {', '.join(iter_sample_data_choices())}"
                )
                raise CommandError(msg)
            requested_keys.add(spec.django_label)

    return [spec for spec in SAMPLE_DATA_SPECS if spec.django_label in requested_keys]


def get_fixture_path(spec: SeedSpec) -> Path:
    return get_sample_data_root() / spec.fixture_file


def get_seed_model(spec: SeedSpec) -> type[models.Model]:
    model = apps.get_model(spec.app_label, spec.model_name)
    if model is None:
        msg = f"Unable to resolve model '{spec.django_label}'."
        raise CommandError(msg)
    return model


def load_fixture_json(spec: SeedSpec) -> list[dict[str, Any]]:
    fixture_path = get_fixture_path(spec)
    if not fixture_path.exists():
        msg = f"Missing sample data file: {fixture_path}"
        raise CommandError(msg)

    with fixture_path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    if not isinstance(raw_data, list):
        msg = f"Sample data file must contain a JSON list: {fixture_path}"
        raise CommandError(msg)

    validated: list[dict[str, Any]] = []
    for entry in raw_data:
        if not isinstance(entry, dict):
            msg = f"Each sample data entry must be an object: {fixture_path}"
            raise CommandError(msg)
        validated.append(entry)

    return validated


def validate_seed_entry(
    entry: dict[str, Any], spec: SeedSpec
) -> tuple[Any, dict[str, Any]]:
    fixture_path = get_fixture_path(spec)

    lookup = entry.get("lookup")
    fields = entry.get("fields", {})
    if not isinstance(lookup, dict):
        msg = f"Each sample data entry requires a lookup object: {fixture_path}"
        raise CommandError(msg)
    if not isinstance(fields, dict):
        msg = f"Each sample data entry requires a fields object: {fixture_path}"
        raise CommandError(msg)

    return resolve_payload(lookup), resolve_payload(fields)


def fetch_image_content(url: str) -> bytes:
    """Download image bytes from a public URL."""
    try:
        with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
            return cast("bytes", response.read())
    except Exception as exc:
        msg = f"Failed to download image from '{url}': {exc}"
        raise CommandError(msg) from exc


def apply_image_url(obj: models.Model, field_name: str, url: str) -> None:
    """Download url and save into obj.<field_name> (an ImageField)."""
    image_field: FieldFile = getattr(obj, field_name)
    filename = url.split("?", maxsplit=1)[0].rstrip("/").split("/")[-1]
    if not filename or "." not in filename:
        filename = f"{field_name}_sample.jpg"
    content = fetch_image_content(url)
    image_field.save(filename, ContentFile(content), save=False)


def seed_tree_node(
    model: type[MP_Node],
    lookup: dict[str, Any],
    fields: dict[str, Any],
) -> None:
    image_url: str = cast("str", fields.pop("image_url", "") or "")
    model_objects = cast("Any", model).objects
    obj = model_objects.filter(**lookup).first()
    if obj is None:
        obj = CategoryService.create_root(
            name=cast("str", fields["name"]),
            slug=cast("str | None", fields.get("slug")),
            description=cast("str", fields.get("description", "")),
            is_active=cast("bool", fields.get("is_active", True)),
        )
        for key, value in fields.items():
            if key in {"name", "slug", "description", "is_active"}:
                continue
            setattr(obj, key, value)
        if image_url:
            apply_image_url(obj, "image", image_url)
        obj.save()
        return

    for key, value in fields.items():
        setattr(obj, key, value)
    if image_url:
        apply_image_url(obj, "image", image_url)
    obj.save()


def seed_regular_model(
    model: type[models.Model],
    lookup: dict[str, Any],
    fields: dict[str, Any],
) -> None:
    image_url: str = cast("str", fields.pop("image_url", "") or "")
    model_objects = cast("Any", model).objects
    obj, _ = model_objects.update_or_create(
        **lookup,
        defaults=fields,
    )
    if image_url:
        apply_image_url(obj, "image", image_url)
        obj.save(update_fields=["image"])


def seed_entry(spec: SeedSpec, entry: dict[str, Any]) -> None:
    model = get_seed_model(spec)
    resolved_lookup, resolved_fields = validate_seed_entry(entry, spec)

    if issubclass(model, MP_Node):
        seed_tree_node(model, resolved_lookup, resolved_fields)
        return

    seed_regular_model(model, resolved_lookup, resolved_fields)


def _resolve_reference(value: dict[str, Any]) -> Any:
    ref_model = value.get("$ref")
    if not ref_model:
        return {key: resolve_payload(item) for key, item in value.items()}

    index = build_sample_data_index()
    spec = index.get(normalize_model_key(str(ref_model)))
    if spec is None:
        msg = f"Unknown model reference '{ref_model}'."
        raise CommandError(msg)

    lookup = value.get("lookup", {})
    if not isinstance(lookup, dict):
        msg = "Reference lookups must be JSON objects."
        raise CommandError(msg)

    model = get_seed_model(spec)
    model_objects = cast("Any", model).objects
    return model_objects.get(**resolve_payload(lookup))


def resolve_payload(value: Any) -> Any:
    if isinstance(value, dict):
        if "$ref" in value:
            return _resolve_reference(value)
        return {key: resolve_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_payload(item) for item in value]
    return value


def load_seed_spec(spec: SeedSpec, *, fresh: bool = False) -> int:
    if fresh:
        clear_seed_spec(spec)

    created_or_updated = 0
    for entry in load_fixture_json(spec):
        seed_entry(spec, entry)
        created_or_updated += 1

    return created_or_updated


def clear_seed_spec(spec: SeedSpec) -> int:
    model = get_seed_model(spec)
    model_objects = cast("Any", model).objects
    deleted_count, _ = model_objects.all().delete()
    return int(deleted_count)
