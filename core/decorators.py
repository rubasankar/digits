from __future__ import annotations

from django.contrib.auth.decorators import login_required

require_customer = login_required(login_url="account_login")
