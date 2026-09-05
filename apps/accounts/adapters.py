from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from structlog import get_logger

if TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.http import HttpRequest

from apps.accounts.models import UserAccount


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def post_login(  # noqa: PLR0913
        self,
        request: HttpRequest,
        user: AbstractBaseUser,
        *,
        email_verification: str,
        signal_kwargs: dict[str, Any] | None,
        email: str | None,
        signup: bool,
        redirect_url: str | None,
    ) -> Any:
        from allauth.account import app_settings  # noqa: PLC0415

        if app_settings.PHONE_VERIFICATION_ENABLED and request.user.is_authenticated:
            phone_verified = self.get_phone(user)
            if phone_verified is None:
                return HttpResponseRedirect(reverse("account_change_phone"))
            phone, verified = phone_verified
            if not verified:
                from allauth.account.internal.flows.phone_verification import (  # noqa: PLC0415
                    ChangePhoneVerificationProcess,
                )

                ChangePhoneVerificationProcess.initiate(request, phone)
                return HttpResponseRedirect(reverse("account_verify_phone"))
        return super().post_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )

    def get_phone(self, user: AbstractBaseUser) -> tuple[str, bool] | None:
        if not isinstance(user, UserAccount):
            return None
        if not user.phone:
            return None
        return (str(user.phone), user.phone_verified)

    def set_phone(
        self,
        user: AbstractBaseUser,
        phone: str,
        verified: bool,  # noqa: FBT001 - allauth adapter interface
    ) -> None:
        if not isinstance(user, UserAccount):
            return
        user.phone = phone
        user.phone_verified = verified
        user.save(update_fields=["phone", "phone_verified"])

    def set_phone_verified(self, user: AbstractBaseUser, phone: str) -> None:
        if not isinstance(user, UserAccount):
            return
        user.phone = phone
        user.phone_verified = True
        user.save(update_fields=["phone", "phone_verified"])

    def get_user_by_phone(self, phone: str) -> UserAccount | None:
        return UserAccount.objects.filter(phone=phone).first()

    def send_verification_code_sms(
        self,
        user: UserAccount,
        phone: str,
        code: str,
        **kwargs: Any,
    ) -> None:
        from apps.accounts.service.sms import send_sms  # noqa: PLC0415
        from apps.accounts.service.sms.message import SMSMessage  # noqa: PLC0415

        send_sms(
            SMSMessage(
                to=str(phone),
                body=_("Your verification code is {code}.").format(code=code),
                code=code,
            )
        )
        logger = get_logger("accounts.adapter")
        logger.info(
            "sms_verification_code_sent",
            phone=str(phone),
            user_id=user.id,
            code=str(code),
            code_sent=True,
        )

    def phone_form_field(self, **kwargs: Any) -> Any:
        from allauth.account.fields import PhoneField  # noqa: PLC0415

        field = PhoneField(**kwargs)
        field.widget.attrs.update(
            {
                "placeholder": _("Enter your phone number"),
            }
        )
        return field


class SocialAccountAdapter(DefaultSocialAccountAdapter):  # type: ignore[misc]
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)
