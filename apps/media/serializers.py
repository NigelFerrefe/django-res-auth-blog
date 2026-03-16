import datetime
from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
from google.cloud import storage
from .models import Media


class MediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = "__all__"

    def get_url(self, obj):
        if not obj.key:
            return None
        
        client = storage.Client()
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(obj.key)
        
        # URL firmada que expira en 60 segundos
        signed_url = blob.generate_signed_url(
            expiration=datetime.timedelta(seconds=60),
            method="GET",
            version="v4"
        )
        return signed_url