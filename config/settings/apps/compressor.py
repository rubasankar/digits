"""
django-compressor configuration.
"""

COMPRESSOR_APPS = [
    "compressor",
]

COMPRESSOR_STATICFILES_FINDERS = [
    "compressor.finders.CompressorFinder",
]
