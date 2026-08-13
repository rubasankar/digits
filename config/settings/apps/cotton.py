"""
django-cotton configuration.
"""

COTTON_APPS = [
    "django_cotton",
]

COTTON_TEMPLATE_LOADERS = [
    "django_cotton.cotton_loader.Loader",
]

COTTON_TEMPLATE_BUILTINS = [
    "django_cotton.templatetags.cotton",
]
