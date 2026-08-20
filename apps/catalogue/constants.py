# Upload paths
BRAND_LOGO_UPLOAD_PATH: str = "brands/"
CATEGORY_IMAGE_UPLOAD_PATH: str = "categories/"
PRODUCT_IMAGE_UPLOAD_PATH: str = "products/"

# Image processing -- dimensions (pixels) and JPEG quality (0-100)
IMAGE_THUMBNAIL_SIZE: tuple[int, int] = (300, 300)
IMAGE_THUMBNAIL_QUALITY: int = 85

IMAGE_MEDIUM_SIZE: tuple[int, int] = (600, 600)
IMAGE_MEDIUM_QUALITY: int = 90

IMAGE_LARGE_SIZE: tuple[int, int] = (1200, 1200)
IMAGE_LARGE_QUALITY: int = 95

IMAGE_FORMAT: str = "JPEG"


# Field length limits
NAME_MAX_LENGTH: int = 150
SLUG_MAX_LENGTH: int = 200
ATTRIBUTE_NAME_MAX_LENGTH: int = 100
ATTRIBUTE_LABEL_MAX_LENGTH: int = 100
ATTRIBUTE_UNIT_DIMENSION_MAX_LENGTH: int = 20
ATTRIBUTE_UNIT_SYMBOL_MAX_LENGTH: int = 30
ATTRIBUTE_VALUE_MAX_LENGTH: int = 500
SKU_MAX_LENGTH: int = 100
PRODUCT_TYPE_MAX_LENGTH: int = 20
FULFILMENT_TYPE_MAX_LENGTH: int = 25
ATTRIBUTE_SCOPE_MAX_LENGTH: int = 7
ATTRIBUTE_VALUE_TYPE_MAX_LENGTH: int = 20


# Attribute value validation limits
LONG_TEXT_MAX_LENGTH: int = 10_000
MULTI_SELECT_MAX_OPTIONS: int = 20
MULTI_SELECT_SEPARATOR: str = ","


# Database constraint names
CONSTRAINT_UNIQUE_ATTRIBUTE_NAME: str = "unique_attribute_definition_name"
CONSTRAINT_UNIQUE_ATTRIBUTE_OPTION_VALUE: str = "unique_attribute_option_value"
CONSTRAINT_UNIQUE_PRODUCT_ATTRIBUTE_VALUE: str = "unique_product_attribute_value"
CONSTRAINT_UNIQUE_VARIANT_ATTRIBUTE_VALUE: str = "unique_variant_attribute_value"
CONSTRAINT_UNIQUE_VARIANT_SKU: str = "unique_product_variant_sku"
CONSTRAINT_IMAGE_DISPLAY_ORDER_NON_NEGATIVE: str = (
    "catalogue_image_display_order_non_negative"
)
CONSTRAINT_UNIT_SYMBOL_REQUIRES_DIMENSION: str = (
    "catalogue_unit_symbol_requires_dimension"
)
