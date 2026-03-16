from io import BytesIO
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException, NotFound
from rest_framework import permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from django.utils import timezone
import pyotp
import qrcode
from utils.ip_utils import get_client_ip
from core.permissions import HasValidAPIKey

User = get_user_model()


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
            return Response({"error": "QR Code or OTP Base32 not found for user"}, status=400)  

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
            return Response({"error": "QR Code or OTP Base32 not found for user"}, status=400)

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
        email = request.data.get('email')
        otp_code = request.data.get('otp')

        if not email or not otp_code:
            return Response({"error": "Both email and OTP code are required."}, status=400)

        try:
            user = User.objects.get(email=email)

            totp = pyotp.TOTP(user.otp_base32)
            if not totp.verify(otp_code):
                return Response({"error": "Invalid OTP code."}, status=400)

            user.login_otp_used = True
            user.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            })

        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)