from django.db import models
from django.utils.translation import gettext_lazy as _


class UnitDimension(models.TextChoices):
    NONE = ("none", _("None / Dimensionless"))
    MASS = ("mass", _("Mass (weight)"))
    LENGTH = ("length", _("Length"))
    AREA = ("area", _("Area"))
    VOLUME = ("volume", _("Volume"))
    TEMPERATURE = ("temperature", _("Temperature"))
    POWER = ("power", _("Power"))
    ENERGY = ("energy", _("Energy"))
    VOLTAGE = ("voltage", _("Voltage"))
    CURRENT = ("current", _("Electric Current"))
    FREQUENCY = ("frequency", _("Frequency"))
    SPEED = ("speed", _("Speed"))
    PRESSURE = ("pressure", _("Pressure"))
    STORAGE = ("storage", _("Digital Storage"))
    TIME = ("time_unit", _("Time"))
    LUMINOUS_FLUX = ("luminous_flux", _("Luminous Flux (brightness)"))
    ANGLE = ("angle", _("Angle"))
    CONCENTRATION = ("concentration", _("Concentration / Density"))
    QUANTITY = ("quantity", _("Quantity / Count"))


# UNITS_BY_DIMENSION
#
# Maps each UnitDimension value -> list of (pint_symbol, display_label) tuples.
# pint_symbol must be parseable by pint's default UnitRegistry.
# display_label is the human-readable string shown in the admin dropdown.
#
# Rules for curating this list:
#  - Include the SI base unit first (it is used as the canonical comparison unit).
#  - Include the most common practical units for a product catalogue.
#  - Omit esoteric units that staff would never encounter.


UNITS_BY_DIMENSION: dict[str, list[tuple[str, str]]] = {
    UnitDimension.NONE: [
        ("", "- no unit -"),
        ("percent", "%"),
        ("ppm", "ppm"),
        ("dimensionless", "dimensionless"),
    ],
    UnitDimension.MASS: [
        ("gram", "g"),
        ("kilogram", "kg"),
        ("milligram", "mg"),
        ("metric_ton", "t (metric ton)"),
        ("pound", "lb"),
        ("ounce", "oz"),
    ],
    UnitDimension.LENGTH: [
        ("meter", "m"),
        ("centimeter", "cm"),
        ("millimeter", "mm"),
        ("kilometer", "km"),
        ("inch", "in"),
        ("foot", "ft"),
        ("yard", "yd"),
    ],
    UnitDimension.AREA: [
        ("meter ** 2", "m²"),
        ("centimeter ** 2", "cm²"),
        ("millimeter ** 2", "mm²"),
        ("kilometer ** 2", "km²"),
        ("inch ** 2", "in²"),
        ("foot ** 2", "ft²"),
        ("hectare", "ha"),
        ("acre", "ac"),
    ],
    UnitDimension.VOLUME: [
        ("liter", "L"),
        ("milliliter", "mL"),
        ("centiliter", "cL"),
        ("deciliter", "dL"),
        ("cubic_meter", "m³"),
        ("cubic_centimeter", "cm³"),
        ("cubic_inch", "in³"),
        ("fluid_ounce", "fl oz"),
        ("gallon", "gal"),
        ("pint", "pt"),
    ],
    UnitDimension.TEMPERATURE: [
        ("degC", "°C"),
        ("degF", "°F"),
        ("kelvin", "K"),
    ],
    UnitDimension.POWER: [
        ("watt", "W"),
        ("kilowatt", "kW"),
        ("megawatt", "MW"),
        ("milliwatt", "mW"),
        ("horsepower", "hp"),
        ("BTU / hour", "BTU/h"),
    ],
    UnitDimension.ENERGY: [
        ("joule", "J"),
        ("kilojoule", "kJ"),
        ("watt_hour", "Wh"),
        ("kilowatt_hour", "kWh"),
        ("megawatt_hour", "MWh"),
        ("calorie", "cal"),
        ("kilocalorie", "kcal"),
        ("BTU", "BTU"),
    ],
    UnitDimension.VOLTAGE: [
        ("volt", "V"),
        ("millivolt", "mV"),
        ("kilovolt", "kV"),
    ],
    UnitDimension.CURRENT: [
        ("ampere", "A"),
        ("milliampere", "mA"),
        ("microampere", "µA"),
    ],
    UnitDimension.FREQUENCY: [
        ("hertz", "Hz"),
        ("kilohertz", "kHz"),
        ("megahertz", "MHz"),
        ("gigahertz", "GHz"),
        ("revolutions_per_minute", "RPM"),
    ],
    UnitDimension.SPEED: [
        ("meter / second", "m/s"),
        ("kilometer / hour", "km/h"),
        ("mile / hour", "mph"),
        ("knot", "kn"),
    ],
    UnitDimension.PRESSURE: [
        ("pascal", "Pa"),
        ("kilopascal", "kPa"),
        ("megapascal", "MPa"),
        ("bar", "bar"),
        ("millibar", "mbar"),
        ("psi", "psi"),
        ("atmosphere", "atm"),
    ],
    UnitDimension.STORAGE: [
        ("byte", "B"),
        ("kilobyte", "kB"),
        ("megabyte", "MB"),
        ("gigabyte", "GB"),
        ("terabyte", "TB"),
        ("petabyte", "PB"),
        ("kibibyte", "KiB"),
        ("mebibyte", "MiB"),
        ("gibibyte", "GiB"),
        ("tebibyte", "TiB"),
    ],
    UnitDimension.TIME: [
        ("second", "s"),
        ("minute", "min"),
        ("hour", "h"),
        ("day", "day"),
        ("week", "week"),
        ("month", "month"),
        ("year", "year"),
        ("millisecond", "ms"),
        ("microsecond", "µs"),
        ("nanosecond", "ns"),
    ],
    UnitDimension.LUMINOUS_FLUX: [
        ("lumen", "lm"),
        ("candela", "cd"),
        ("lux", "lx"),
    ],
    UnitDimension.ANGLE: [
        ("degree", "°"),
        ("radian", "rad"),
        ("arcminute", "'"),
        ("arcsecond", '"'),
    ],
    UnitDimension.CONCENTRATION: [
        ("kilogram / liter", "kg/L"),
        ("gram / liter", "g/L"),
        ("milligram / liter", "mg/L"),
        ("gram / milliliter", "g/mL"),
        ("kilogram / cubic_meter", "kg/m³"),
        ("gram / cubic_centimeter", "g/cm³"),
    ],
    UnitDimension.QUANTITY: [
        ("piece", "pc (piece)"),
        ("dozen", "doz (dozen)"),
        ("pair", "pair"),
        ("gross", "gross (144)"),
        ("set", "set"),
        ("pack", "pack"),
        ("roll", "roll"),
        ("sheet", "sheet"),
        ("box", "box"),
        ("carton", "carton"),
    ],
}


class AttributeScope(models.TextChoices):
    PRODUCT = ("product", _("Product-level"))
    VARIANT = ("variant", _("Variant-level"))


class AttributeValueType(models.TextChoices):
    TEXT = ("text", _("Text"))
    LONG_TEXT = ("long_text", _("Long Text"))
    INTEGER = ("integer", _("Integer"))
    BIG_INTEGER = ("big_integer", _("Big Integer"))
    DECIMAL = ("decimal", _("Decimal"))
    FLOAT = ("float", _("Float"))
    BOOLEAN = ("boolean", _("Boolean"))
    DATE = ("date", _("Date"))
    TIME = ("time", _("Time"))
    DATETIME = ("datetime", _("Date & Time"))
    JSON = ("json", _("JSON"))
    UUID = ("uuid", _("UUID"))
    EMAIL = ("email", _("Email"))
    URL = ("url", _("URL"))
    COLOR = ("color", _("Colour"))
    SINGLE_SELECT = ("single_select", _("Single Select"))
    MULTI_SELECT = ("multi_select", _("Multi Select"))


NUMERIC_VALUE_TYPES: frozenset[str] = frozenset(
    {
        AttributeValueType.INTEGER,
        AttributeValueType.BIG_INTEGER,
        AttributeValueType.DECIMAL,
        AttributeValueType.FLOAT,
    }
)

TEXT_VALUE_TYPES: frozenset[str] = frozenset(
    {
        AttributeValueType.TEXT,
        AttributeValueType.LONG_TEXT,
        AttributeValueType.EMAIL,
        AttributeValueType.URL,
        AttributeValueType.UUID,
    }
)

SELECT_VALUE_TYPES: frozenset[str] = frozenset(
    {
        AttributeValueType.SINGLE_SELECT,
        AttributeValueType.MULTI_SELECT,
    }
)

DATE_VALUE_TYPES: frozenset[str] = frozenset(
    {
        AttributeValueType.DATE,
        AttributeValueType.TIME,
        AttributeValueType.DATETIME,
    }
)


class ProductType(models.TextChoices):
    PHYSICAL = ("physical", _("Physical Product"))
    DIGITAL = ("digital", _("Digital Download"))
    SUBSCRIPTION = ("subscription", _("Subscription"))
    SERVICE = ("service", _("Service"))
    MEMBERSHIP = ("membership", _("Membership"))
    GIFT_CARD = ("gift_card", _("Gift Card"))
    DONATION = ("donation", _("Donation"))
    EVENT = ("event", _("Event Ticket"))
    COURSE = ("course", _("Online Course"))
    SOFTWARE_LICENSE = ("software_license", _("Software License"))
    BUNDLE = ("bundle", _("Bundle"))
    PRE_ORDER = ("pre_order", _("Pre-order"))
    RENTAL = ("rental", _("Rental"))


class FulfilmentType(models.TextChoices):
    SHIPMENT = ("shipment", _("Shipment"))
    LOCAL_DELIVERY = ("local_delivery", _("Local Delivery"))
    STORE_PICKUP = ("store_pickup", _("Store Pickup"))
    DOWNLOAD = ("download", _("Download"))
    EMAIL = ("email", _("Email Delivery"))
    LICENSE_KEY = ("license_key", _("License Key"))
    STREAMING = ("streaming", _("Streaming Access"))
    ACCOUNT_PROVISION = ("account_provision", _("Account Provisioning"))
    SUBSCRIPTION = ("subscription", _("Recurring Subscription"))
    SERVICE_APPOINTMENT = ("service_appointment", _("Service Appointment"))
    EVENT_ACCESS = ("event_access", _("Event Access"))
    MANUAL = ("manual", _("Manual Fulfilment"))
