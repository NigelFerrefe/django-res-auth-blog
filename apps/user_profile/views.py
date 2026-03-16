from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model
from core.permissions import HasValidAPIKey
from .models import UserProfile
from .serializers import UserProfileSerializer

User = get_user_model()

class MyUserProfileView(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            user_profile = UserProfile.objects.get(user=request.user)
            serialized_user_profile = UserProfileSerializer(user_profile).data
            return Response(serialized_user_profile)
        except UserProfile.DoesNotExist:
            raise NotFound(detail="User profile not found")