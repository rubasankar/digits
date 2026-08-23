"""Root pytest configuration"""

import os

from hypothesis import settings

settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=500)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
