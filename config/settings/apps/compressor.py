"""
django-compressor configuration.
Production-specific settings (COMPRESS_ENABLED, COMPRESS_OFFLINE, filters,
storage backend) live in production.py.
"""

COMPRESSOR_APPS = [
    "compressor",
]

COMPRESSOR_STATICFILES_FINDERS = [
    "compressor.finders.CompressorFinder",
]
