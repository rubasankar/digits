from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from apps.catalogue.constants import BRAND_LOGO_UPLOAD_PATH
from apps.catalogue.constants import FULFILMENT_TYPE_MAX_LENGTH
from apps.catalogue.constants import IMAGE_FORMAT
from apps.catalogue.constants import IMAGE_LARGE_QUALITY
from apps.catalogue.constants import IMAGE_LARGE_SIZE
from apps.catalogue.constants import IMAGE_MEDIUM_QUALITY
from apps.catalogue.constants import IMAGE_MEDIUM_SIZE
from apps.catalogue.constants import IMAGE_THUMBNAIL_QUALITY
from apps.catalogue.constants import IMAGE_THUMBNAIL_SIZE
from apps.catalogue.constants import PRODUCT_IMAGE_UPLOAD_PATH
from apps.catalogue.constants import PRODUCT_TYPE_MAX_LENGTH
from apps.catalogue.constants import SKU_MAX_LENGTH
from apps.catalogue.enums import FulfilmentType
from apps.catalogue.enums import ProductType
from apps.catalogue.managers import ProductManager
from apps.catalogue.managers import ProductVariantManager
from apps.catalogue.models.category import ProductCategory
from apps.catalogue.validators import validate_sku
from apps.catalogue.validators import validate_type_fulfilment_combination
from core.models import BaseModel


class ProductBrand(BaseModel):
    website = models.URLField(_("Website"), blank=True)
    logo = models.ImageField(
        _("Logo"),
        upload_to=BRAND_LOGO_UPLOAD_PATH,
        blank=True,
    )

    class Meta:
        verbose_name = _("Product Brand")
        verbose_name_plural = _("Product Brands")
        ordering = ["name"]

    def __repr__(self) -> str:
        return f"<ProductBrand id={self.id} name={self.name!r}>"


class Product(BaseModel):
    objects: ProductManager = ProductManager()

    category = models.ForeignKey(
        ProductCategory,
        verbose_name=_("Category"),
        on_delete=models.PROTECT,
        related_name="products",
        help_text=_("Drives which attribute definitions apply to this product."),
        db_index=True,
    )
    brand = models.ForeignKey(
        ProductBrand,
        verbose_name=_("Brand"),
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        db_index=True,
    )
    product_type = models.CharField(
        _("Product Type"),
        max_length=PRODUCT_TYPE_MAX_LENGTH,
        choices=ProductType.choices,
        default=ProductType.PHYSICAL,
        db_index=True,
        help_text=_(
            "Routing key: determines which fulfilment app handles this product. "
            "Contact a developer to add new types."
        ),
    )
    fulfilment_type = models.CharField(
        _("Fulfilment Type"),
        max_length=FULFILMENT_TYPE_MAX_LENGTH,
        choices=FulfilmentType.choices,
        default=FulfilmentType.SHIPMENT,
        db_index=True,
        help_text=_(
            "Routing key: how this product is delivered to the buyer. "
            "Contact a developer to add new fulfilment methods."
        ),
    )
    other_attributes = models.JSONField(
        _("Extra Attributes"),
        default=dict,
        blank=True,
        help_text=_(
            "Arbitrary product-level attributes not covered by the structured "
            "attribute assignment system. Stored as a plain JSON object."
        ),
    )
    is_active = models.BooleanField(_("Active"), default=True, db_index=True)

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["name"]

    def clean(self) -> None:
        super().clean()
        if self.product_type and self.fulfilment_type:
            validate_type_fulfilment_combination(
                self.product_type, self.fulfilment_type
            )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} type={self.product_type}>"


class ProductVariant(UUIDModel, TimeStampedModel):
    objects: ProductVariantManager = ProductVariantManager()

    product = models.ForeignKey(
        Product,
        verbose_name=_("Product"),
        on_delete=models.CASCADE,
        related_name="variants",
        db_index=True,
    )
    sku = models.CharField(
        _("SKU"),
        max_length=SKU_MAX_LENGTH,
        unique=True,
        db_index=True,
        validators=[validate_sku],
        help_text=_("Stock Keeping Unit -- unique across the entire catalogue."),
    )
    other_attributes = models.JSONField(
        _("Extra Attributes"),
        default=dict,
        blank=True,
        help_text=_(
            "Arbitrary variant-level attributes not covered by the structured "
            "attribute assignment system. Stored as a plain JSON object."
        ),
    )

    is_active = models.BooleanField(
        _("Active"),
        default=True,
        db_index=True,
        help_text=_("Inactive variants are hidden from the storefront."),
    )

    class Meta:
        verbose_name = _("Product Variant")
        verbose_name_plural = _("Product Variants")
        ordering = ["product", "sku"]

    def __str__(self) -> str:
        return f"{self.product.name} -- {self.sku}"

    def __repr__(self) -> str:
        return f"<ProductVariant id={self.id} sku={self.sku!r} active={self.is_active}>"


class ProductImage(UUIDModel, TimeStampedModel):
    product_variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(_("Image"), upload_to=PRODUCT_IMAGE_UPLOAD_PATH)
    alt_text = models.CharField(
        _("Alt Text"),
        max_length=255,
        blank=True,
        help_text=_("Describe the image for accessibility and SEO."),
    )

    thumbnail: ImageSpecField = ImageSpecField(
        source="image",
        processors=[ResizeToFill(*IMAGE_THUMBNAIL_SIZE)],
        format=IMAGE_FORMAT,
        options={"quality": IMAGE_THUMBNAIL_QUALITY},
    )
    medium: ImageSpecField = ImageSpecField(
        source="image",
        processors=[ResizeToFill(*IMAGE_MEDIUM_SIZE)],
        format=IMAGE_FORMAT,
        options={"quality": IMAGE_MEDIUM_QUALITY},
    )
    large: ImageSpecField = ImageSpecField(
        source="image",
        processors=[ResizeToFill(*IMAGE_LARGE_SIZE)],
        format=IMAGE_FORMAT,
        options={"quality": IMAGE_LARGE_QUALITY},
    )

    is_primary = models.BooleanField(
        _("Primary Image"),
        default=False,
        help_text=_("Only one image per variant should be primary."),
    )
    display_order = models.PositiveSmallIntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Lower numbers appear first."),
    )

    class Meta:
        verbose_name = _("Product Image")
        verbose_name_plural = _("Product Images")
        ordering = ["product_variant", "display_order"]

    def clean(self) -> None:
        super().clean()
        if self.is_primary and self.product_variant:
            qs = ProductImage.objects.filter(
                product_variant=self.product_variant,
                is_primary=True,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    _("This variant already has a primary image. Unset it first.")
                )

    def __str__(self) -> str:
        label = "(primary)" if self.is_primary else f"#{self.display_order}"
        return f"{self.product_variant} -- image {label}"

    def __repr__(self) -> str:
        return (
            f"<ProductImage id={self.id} variant={self.product_variant} "
            f"primary={self.is_primary}>"
        )
