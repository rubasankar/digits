"""
django-allauth configuration.
Covers: account (core), headless (JSON API), mfa, and socialaccount.
"""

from .environ import env

ALLAUTH_APPS = [
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

ALLAUTH_MIDDLEWARE = [
    "allauth.account.middleware.AccountMiddleware",
]

# Core account
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_MAX_EMAIL_ADDRESSES = 2
ACCOUNT_UNIQUE_EMAIL = True

ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
ACCOUNT_FORMS = {"signup": "apps.accounts.forms.UserSignupForm"}

DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)
ALLAUTH_SITES_ENABLED = False

# Headless (JSON API)
# "sessions" issues a cookie-based session token -- suitable for SSR or a
# same-domain SPA. Switch to "jwt" for mobile / cross-domain clients.
HEADLESS_TOKEN_STRATEGY = env(
    "HEADLESS_TOKEN_STRATEGY",
    default="allauth.headless.tokens.sessions",
)

# Frontend URLs embedded in verification / password-reset emails.
# Override per environment (local.py / production.py) to point at your
# actual frontend routes.
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "/auth/confirm-email/{key}/",
    "account_reset_password": "/auth/password/reset/",
    "account_reset_password_from_key": "/auth/password/reset/key/{key}/",
    "socialaccount_login_error": "/auth/social/error/",
}

# MFA
MFA_TOTP_PERIOD = 30
MFA_TOTP_DIGITS = 6
MFA_RECOVERY_CODE_COUNT = 10

# Social account
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "apps.accounts.forms.UserSocialSignupForm"}

# Auto-connect a social login to an existing account that shares the same
# verified email -- safe because email verification is mandatory.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True


SOCIALACCOUNT_PROVIDERS: dict[str, dict[str, object]] = {
    "google": {
        "APP": {"client_id": env("GOOGLE_CLIENT_ID"), "secret": env("GOOGLE_SECRET")},
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "OAUTH_PKCE_ENABLED": True,
    },
}
