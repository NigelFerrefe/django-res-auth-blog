from rest_framework import serializers
from apps.media.serializers import MediaSerializer
from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    profile_picture = MediaSerializer()
    banner_picture = MediaSerializer()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "bio",
            "instagram",
            "linkedin",
            "birthday",
            "profile_picture",
            "banner_picture",
        ]
