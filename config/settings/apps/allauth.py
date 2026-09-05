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
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*", "phone"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_MAX_EMAIL_ADDRESSES = 2
ACCOUNT_UNIQUE_EMAIL = True

# Phone verification
ACCOUNT_PHONE_VERIFICATION_ENABLED = env.bool(
    "ACCOUNT_PHONE_VERIFICATION_ENABLED", True
)
ACCOUNT_PHONE_VERIFICATION_TIMEOUT = 900
ACCOUNT_PHONE_VERIFICATION_MAX_ATTEMPTS = 3
ACCOUNT_PHONE_VERIFICATION_SUPPORTS_RESEND = True
ACCOUNT_PHONE_VERIFICATION_SUPPORTS_CHANGE = True
ACCOUNT_PHONE_VERIFICATION_CODE_FORMAT = {"numeric": True, "length": 6, "dashed": False}

ACCOUNT_RATE_LIMITS = {
    # Change phone number: allow a few retries per minute without blocking
    "change_phone": "5/m/user",
    # Verify phone: keep a per-key cool-down, but don't block per-IP too hard
    "verify_phone": "1/30s/key,10/m/ip",
}

# SMS delivery backend for phone verification.
#   - Development:   apps.accounts.service.sms.backends.ConsoleSMSBackend
#   - Production:    a concrete provider backend (e.g. Twilio/Vonage). Until one
#                    is wired in, ProviderSMSBackend raises on send and forces
#                    an env override rather than silently dropping messages.
ACCOUNT_SMS_BACKEND = env(
    "ACCOUNT_SMS_BACKEND",
    default="apps.accounts.service.sms.backends.ConsoleSMSBackend",
)

ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
ACCOUNT_FORMS = {"signup": "apps.accounts.forms.UserSignupForm"}

DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)
ALLAUTH_SITES_ENABLED = False

# Headless (JSON API)
HEADLESS_TOKEN_STRATEGY = env(
    "HEADLESS_TOKEN_STRATEGY",
    default="allauth.headless.tokens.sessions",
)

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

# Auto-connect social login to existing account sharing same verified email
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
