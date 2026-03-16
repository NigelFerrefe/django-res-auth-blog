import uuid
from django.db import models
from django.conf import settings
from tinymce.models import HTMLField
from djoser.signals import user_registered, user_activated
from apps.media.models import Media
User = settings.AUTH_USER_MODEL


class UserProfile(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = HTMLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    profile_picture = models.ForeignKey(
        Media,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profile_picture"
    )
    banner_picture = models.ForeignKey(
        Media,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="banner_picture"
    )

#def post_user_registered(user, *args, **kwargs):
#    print("user has registered")


def post_user_activated(user, *args, **kwargs):
   profile = UserProfile.objects.create(user=user)
   profile_picture = Media.objects.create(
       order=1,
       name="user-icon-placeholder",
       size="21.7 KB",
       type="png",
       key="media/profiles/default/user-icon-placeholder.png",
       media_type="image",
   )
   banner_picture = Media.objects.create(
       order=1,
       name="banner",
       size="1.7 KB",
       type="png",
       key="media/profiles/default/banner.png",
       media_type="image",
   )
   profile.profile_picture = profile_picture
   profile.banner_picture = banner_picture
   profile.save()

#user_registered.connect(post_user_registered)
user_activated.connect(post_user_activated)
