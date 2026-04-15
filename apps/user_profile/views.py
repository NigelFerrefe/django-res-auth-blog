from datetime import datetime, timedelta
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from core.permissions import HasValidAPIKey
from apps.authentication.serializers import UserPublicSerializer
from .models import UserProfile
from .serializers import UserProfileSerializer
from utils.string_utils import sanitize_string, sanitize_html, sanitize_url
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from google.cloud import storage
from .models import Media

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


class DetailUserProfileView(APIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        username = request.query_params.get("username")
        if not username:
            return Response(
                {"error": "A valid username must be provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "user": UserPublicSerializer(user).data,
                "profile": UserProfileSerializer(user_profile).data,
            },
            status=status.HTTP_200_OK,
        )


class GetMyProfilePictureView(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not profile.profile_picture:
            return Response(
                {"error": "No profile picture found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            client = storage.Client()
            bucket = client.bucket(settings.GS_BUCKET_NAME)
            blob = bucket.blob(profile.profile_picture.key)
            signed_url = blob.generate_signed_url(
                expiration=timedelta(seconds=60),
                method="GET",
                version="v4",
            )
            return Response(signed_url, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Error fetching image from GCS."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetMyBannerPictureView(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not profile.banner_picture:
            return Response(
                {"error": "No banner picture found."}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            client = storage.Client()
            bucket = client.bucket(settings.GS_BUCKET_NAME)
            blob = bucket.blob(profile.banner_picture.key)
            signed_url = blob.generate_signed_url(
                expiration=timedelta(seconds=60),
                method="GET",
                version="v4",
            )
            return Response(signed_url, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Error fetching image from GCS."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


PROTECTED_KEYS = {
    "media/profiles/default/banner.png",
    "media/profiles/default/user-icon-placeholder.png",
}


class UploadProfilePictureView(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        key = request.data.get("key")
        title = request.data.get("title")
        size = request.data.get("size")
        file_type = request.data.get("type")

        if not all([key, title, size, file_type]):
            return Response(
                {"error": "Missing required fields."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

        client = storage.Client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(key)

        if not blob.exists():
            return Response(
                {"error": "File not found in storage."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.profile_picture:
            try:
                old_key = profile.profile_picture.key
                if old_key not in PROTECTED_KEYS:
                    old_blob = bucket.blob(old_key)
                    if old_blob.exists():
                        old_blob.delete()
            except Exception:
                pass

            profile.profile_picture.delete()

        profile_picture = Media.objects.create(
            order=0,
            name=title,
            size=size,
            type=file_type,
            key=key,
            media_type="image",
        )
        profile.profile_picture = profile_picture
        profile.save()

        return Response(
            {"message": "Profile picture has been updated."}, status=status.HTTP_200_OK
        )


class UploadBannerPictureView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        user = request.user
        key = request.data.get("key")
        title = request.data.get("title")
        size = request.data.get("size")
        file_type = request.data.get("type")

        if not all([key, title, size, file_type]):
            return Response(
                {"error": "Missing required fields."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND
            )

        client = storage.Client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(key)

        if not blob.exists():
            return Response(
                {"error": "File not found in storage."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.banner_picture:
            try:
                old_key = profile.banner_picture.key
                if old_key not in PROTECTED_KEYS:
                    old_blob = bucket.blob(old_key)
                    if old_blob.exists():
                        old_blob.delete()
            except Exception:
                pass

            profile.banner_picture.delete()

        banner_picture = Media.objects.create(
            order=0,
            name=title,
            size=size,
            type=file_type,
            key=key,
            media_type="image",
        )
        profile.banner_picture = banner_picture
        profile.save()

        return Response(
            {"message": "Banner picture has been updated."}, status=status.HTTP_200_OK
        )


class UpdateUserProfileView(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request):
        try:
            profile = UserProfile.objects.get(user=request.user)

            bio = request.data.get("bio", None)
            instagram = request.data.get("instagram", None)
            linkedin = request.data.get("linkedin", None)
            birthday = request.data.get("birthday", None)

            if bio:
                profile.bio = sanitize_html(bio)
            if instagram:
                profile.instagram = sanitize_url(instagram)
            if linkedin:
                profile.linkedin = sanitize_url(linkedin)
            if birthday:
                try:
                    formatted_birthday = datetime.strptime(birthday, "%Y-%m-%d").date()
                    profile.birthday = formatted_birthday
                except ValueError:
                    raise ValidationError("Invalid date format. Use YYYY-MM-DD.")

            profile.save()

            return Response(
                {"message": "Profile information updated successfully"},
                status=status.HTTP_200_OK,
            )
        except UserProfile.DoesNotExist:
            raise NotFound(detail="User profile not found")
