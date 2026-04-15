from django.urls import path

from .views import (
    GenerateQRCodeView,
    OTPLoginResetView,
    VerifyOTPView,
    DisableOTPView,
    Set2FAView,
    OTPLoginView,
    SendOTPLoginView,
    VerifyOTPLoginView,
    LoginView,
    UpdateUserInformationView
)


urlpatterns = [
    path(
        "generate_qr_code/",
        GenerateQRCodeView.as_view(),
        name="generate-qr-code-view",
    ),
    path("otp_login_reset/", OTPLoginResetView.as_view(), name="otp-login-reset-view"),
    path("verify_otp/", VerifyOTPView.as_view()),
    path("disable_otp/", DisableOTPView.as_view()),
    path("confirm_2fa/", Set2FAView.as_view()),
    path("otp_login/", OTPLoginView.as_view()),
    path("send_otp_login/", SendOTPLoginView.as_view()),
    path("verify_otp_login/", VerifyOTPLoginView.as_view()),
    path("login/", LoginView.as_view(), name="login-view"),
    path("update_user/", UpdateUserInformationView.as_view(), name="update-user"),
]
