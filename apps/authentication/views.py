from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException, NotFound
from rest_framework import permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.contrib.auth import get_user_model, authenticate
from django.core.files.base import ContentFile
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.sites.models import Site
import pyotp
import qrcode
from utils.ip_utils import get_client_ip
from core.permissions import HasValidAPIKey
from utils.string_utils import sanitize_string, sanitize_username
User = get_user_model()

class UpdateUserInformationView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasValidAPIKey]

    def patch(self, request):
        user = request.user

        username = request.data.get("username")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")

        if not any([username, first_name, last_name]):
            return Response(
                {"error": "At least one field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if username:
            user.username = sanitize_username(username)

        if first_name:
            user.first_name = sanitize_string(first_name)

        if last_name:
            user.last_name = sanitize_string(last_name)

        user.save()

        return Response(
            {"message": "User information updated successfully"},
            status=status.HTTP_200_OK
        )

class GenerateQRCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasValidAPIKey]

    def get(self, request):
        user = request.user
        email = user.email

        otp_base32 = pyotp.random_base32()
        otp_auth_url = pyotp.totp.TOTP(otp_base32).provisioning_uri(
            name=email.lower(), issuer_name="Nigel"
        )
        stream = BytesIO()
        image = qrcode.make(f"{otp_auth_url}")
        image.save(stream)
        user.otp_base32 = otp_base32
        user.qr_code = ContentFile(
            stream.getvalue(), name=f"qr{get_random_string(10)}.png"
        )
        user.save()
        qr_code = user.qr_code
        return Response(qr_code.url)


class OTPLoginResetView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasValidAPIKey]

    def post(self, request):
        user = request.user
        new_ip = get_client_ip(request)
        if user.login_ip and user.login_ip != new_ip:
            print(f"New login IP for user: {user.email}")

        user.login_ip = new_ip
        if user.qr_code is None or user.otp_base32 is None:
            return Response({"error": "QR Code or OTP Base32 not found"}, status=400)

        try:
            totp = pyotp.TOTP(user.otp_base32).now()
        except Exception as e:
            raise APIException(detail=f"Error generating TOTP: {str(e)}")

        user.login_otp = make_password(totp)
        user.otp_created_at = timezone.now()
        user.login_otp_used = False

        user.save()

        return Response({"message": "OTP Reset Successfully"})


class VerifyOTPView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasValidAPIKey]

    def post(self, request):
        user = request.user

        if user.qr_code is None or user.otp_base32 is None:
            return Response(
                {"error": "QR Code or OTP Base32 not found for user"}, status=400
            )

        totp = pyotp.TOTP(user.otp_base32)
        otp = request.data.get("otp")

        if not otp:
            return Response({"error": "OTP is required"}, status=400)

        verified = totp.verify(otp)

        if verified:
            user.login_otp_used = True
            user.save()
            return Response({"message": "OTP Verified"})
        else:
            return Response({"error": "Error Verifying One Time Password"}, status=400)


class DisableOTPView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasValidAPIKey]

    def post(self, request):
        user = request.user

        if user.qr_code is None or user.otp_base32 is None:
            return Response(
                {"error": "QR Code or OTP Base32 not found for user"}, status=400
            )

        totp = pyotp.TOTP(user.otp_base32)
        otp = request.data.get("otp")

        if not otp:
            return Response({"error": "OTP is required"}, status=400)

        verified = totp.verify(otp)

        if verified:
            user.two_factor_enabled = False
            user.otpauth_url = None
            user.otp_base32 = None
            user.qr_code = None
            user.login_otp = None
            user.login_otp_used = False
            user.otp_created_at = None
            user.save()
            return Response({"message": "Two Factor Authentication Disabled"})
        else:
            return Response({"error": "Error Verifying One Time Password"}, status=400)


class Set2FAView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasValidAPIKey]

    def post(self, request, *args, **kwargs):
        user = request.user

        if user.qr_code is None:
            return Response({"error": "QR Code not found for the user."}, status=400)

        boolean = bool(request.data.get("bool"))

        if boolean:
            user.two_factor_enabled = True
            user.save()
            return Response({"message": "2FA Activated"})
        else:
            user.two_factor_enabled = False
            user.save()
            return Response({"message": "2FA Disabled"})


# Login when user has activated 2FA
class OTPLoginView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        email = request.data.get("email")
        otp_code = request.data.get("otp")

        if not email or not otp_code:
            return Response(
                {"error": "Both email and OTP code are required."}, status=400
            )

        try:
            user = User.objects.get(email=email)

            totp = pyotp.TOTP(user.otp_base32)
            if not totp.verify(otp_code):
                return Response({"error": "Invalid OTP code."}, status=400)

            user.login_otp_used = True
            user.save()

            refresh = RefreshToken.for_user(user)
            return Response(
                {"access": str(refresh.access_token), "refresh": str(refresh)}
            )

        except User.DoesNotExist:
            return Response(
                {"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND
            )


class SendOTPLoginView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        email = request.data.get("email")

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "User does not exist or is not active."},
                status=status.HTTP_404_NOT_FOUND,
            )

        secret = pyotp.random_base32()
        user.otp_base32 = secret
        user.save()

        totp = pyotp.TOTP(secret)
        otp = totp.now()

        site = Site.objects.get_current()
        domain = site.domain

        send_mail(
            "Your OTP Code",
            f"Your OTP code is {otp}",
            f"noreply@{domain}",
            [email],
            fail_silently=False,
        )

        return Response(
            {"message": "OTP sent successfully."}, status=status.HTTP_200_OK
        )


class VerifyOTPLoginView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        email = request.data.get("email")
        otp_code = request.data.get("otp")

        if not email or not otp_code:
            return Response(
                {"error": "Both email and OTP code are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": "User does not exist or is not active."},
                status=status.HTTP_404_NOT_FOUND,
            )

        totp = pyotp.TOTP(user.otp_base32)

        if not totp.verify(otp_code):
            return Response(
                {"error": "Error verifying OTP code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )




class LoginView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, email=email, password=password)

        if not user:
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            return Response(
                {"error": "Account is not active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.two_factor_enabled:
            return Response({
                "two_factor_required": True,
                "email": email
            }, status=status.HTTP_200_OK)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_200_OK)