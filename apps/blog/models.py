import uuid
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from django.utils.html import format_html
from apps.media.models import Media
from apps.media.serializers import MediaSerializer
from tinymce.models import HTMLField
from django.conf import settings
from .utils import get_client_ip

User = settings.AUTH_USER_MODEL


def blog_thumbnail_directory(instance, filename):
    return "media/thumbnails/blog/{0}/{1}".format(instance.title, filename)


def category_thumbnail_directory(instance, filename):
    return "media/thumbnails/blog_categories/{0}/{1}".format(instance.name, filename)


# Category with subcategories
class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        "self", related_name="children", on_delete=models.CASCADE, blank=True, null=True
    )
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    thumbnail = models.ImageField(
        upload_to=category_thumbnail_directory, blank=True, null=True
    )
    slug = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class CategoryView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="category_view"
    )
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)


class CategoryAnalytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.OneToOneField(
        Category, on_delete=models.CASCADE, related_name="category_analytics"
    )
    views = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    click_through_rate = models.FloatField(default=0)  # Promedio de clicks por vistas
    avg_time_on_page = models.FloatField(
        default=0
    )  # Cuanto tiempo pasa una persona leyendo el post

    def _update_click_through_rate(self):
        if self.impressions > 0:
            self.click_through_rate = (self.clicks / self.impressions) * 100
        else:
            self.click_through_rate = 0
        self.save()

    def increment_click(self):
        self.clicks += 1
        self.save()
        self._update_click_through_rate()

    def increment_impression(self):
        self.impressions += 1
        self.save()
        self._update_click_through_rate()

    def increment_view(self, ip_address):
        try:
            CategoryView.objects.create(category=self.category, ip_address=ip_address)
            self.views += 1
            self.save()
        except Exception:
            pass


class Post(models.Model):

    class PostObjects(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(status="published")

    status_options = (
        ("draft", "Draft"),
        ("published", "Published"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="user_post"
    )  # Post se queda como nulo si el usuario se ha borrado
    title = models.CharField(max_length=128)
    description = models.CharField(max_length=256)
    content = HTMLField()
    thumbnail = models.ForeignKey(
        Media,
        on_delete=models.SET_NULL,
        related_name="post_thumbnail",
        blank=True,
        null=True,
    )
    featured = models.BooleanField(default=False)
    keywords = models.CharField(max_length=128)
    slug = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.IntegerField(default=0)
    status = models.CharField(max_length=50, choices=status_options, default="draft")
    objects = models.Manager()  # default manager, show all posts
    postobjects = PostObjects()  # custom manager, show published posts
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT
    )  # If category is deleted, preserve the post

    class Meta:
        ordering = ("status", "-created_at")

    def __str__(self):
        return self.title

    def thumbnail_preview(self):
        if self.thumbnail:
            serializer = MediaSerializer(instance=self.thumbnail)
            url = serializer.data.get("url")
            if url:
                return format_html(
                    '<img src="{}" style="width: 100px; height: auto;" />', url
                )
        return "No Thumbnail"

    thumbnail_preview.short_description = "Thumbnail Preview"


# Analytic to keep track about how many times your post has been visited
class PostView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="post_views")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, related_name="post_views_user"
    )
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "ip_address"], name="unique_post_ip_view"
            )
        ]

    def __str__(self):
        return f"View by {self.user.username if self.user else 'Anonymous'} in {self.post.title}"


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="user_comments"
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="post_comments"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    content = HTMLField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"

    def get_replies(self):
        return self.replies.filter(is_active=True)


class PostLike(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, related_name="post_like"
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Like by {self.user.username} on {self.post.title}"


class PostShare(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="post_shares",
        null=True,
        blank=True,
    )
    platform = models.CharField(
        max_length=50,
        choices=(
            ("facebook", "Facebook"),
            ("x", "X"),
            ("linkedin", "LinkedIn"),
            ("whatsapp", "WhatsApp"),
            ("other", "Other"),
        ),
        blank=True,
        null=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Share by {self.user.username if self.user else 'Anonymous'} on {self.post.title} via {self.platform}"


class PostInteraction(models.Model):
    INTERACTION_CHOICES = (
        ("view", "View"),
        ("like", "Like"),
        ("comment", "Comment"),
        ("share", "Share"),
    )

    INTERACTION_TYPE_CATEGORIES = (
        ("passive", "Passive"),
        ("active", "Active"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="user_post_interactions",
    )
    post = models.ForeignKey(
        Post, on_delete=models.SET_NULL, null=True, related_name="post_interactions"
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.SET_NULL, null=True, related_name="interaction"
    )
    interaction_type = models.CharField(max_length=30, choices=INTERACTION_CHOICES)
    interaction_category = models.CharField(
        max_length=10,
        choices=INTERACTION_TYPE_CATEGORIES,
        default="passive",
    )
    weight = models.FloatField(default=1.0)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    hour_of_day = models.IntegerField(null=True, blank=True)  # Hora del día (0-23)
    day_of_week = models.IntegerField(
        null=True, blank=True
    )  # Día de la semana (0=Domingo, 6=Sábado)

    class Meta:
        unique_together = ("user", "post", "interaction_type", "comment")
        ordering = ["-timestamp"]

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        post_title = self.post.title if self.post else "Deleted post"
        return f"{username} {self.interaction_type} {post_title}"

    def detect_anomalies(self, user, post):
        recent_interactions = PostInteraction.objects.filter(
            user=user,
            post=post,
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=10),
        )
        if recent_interactions.count() > 50:  # Limite arbitrario
            raise ValueError("Anomalous behavior detected!")

    def clean(self):
        # Validar que las interacciones tipo "comment" tengan un comentario asociado
        if self.interaction_type == "comment" and not self.comment:
            raise ValueError(
                "Interacciones de tipo 'comment deben tener un comentario asociado'"
            )
        # Validar que las interacciones de tipo "view", "like", "share" no tengan un comentario asociado
        if self.interaction_type in ["view", "like", "share"] and self.comment:
            raise ValueError(
                "Interacciones de tipo 'view', 'like', o 'share' no deben tener un comentario asociado."
            )

    def save(self, *args, **kwargs):
        if self.interaction_type == "view":
            self.interaction_category = "passive"
        else:
            self.interaction_category = "active"

        now = timezone.now()

        self.hour_of_day = now.hour
        self.day_of_week = now.weekday()

        super().save(*args, **kwargs)


# Analytic to get post recommendations
class PostAnalytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.OneToOneField(
        Post, on_delete=models.CASCADE, related_name="post_analytics"
    )
    views = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    click_through_rate = models.FloatField(default=0)  # Promedio de clicks por vistas
    avg_time_on_page = models.FloatField(
        default=0
    )  # Cuanto tiempo pasa una persona leyendo el post
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)

    def _update_click_through_rate(self):
        if self.impressions > 0:
            self.click_through_rate = (self.clicks / self.impressions) * 100
        else:
            self.click_through_rate = 0
        self.save()

    def increment_click(self):
        self.clicks += 1
        self.save()
        self._update_click_through_rate()

    def increment_impression(self):
        self.impressions += 1
        self.save()
        self._update_click_through_rate()

    def increment_view(self, ip_address, user=None):
        if not PostView.objects.filter(
            post=self.post, ip_address=ip_address, user=user
        ).exists():
            PostView.objects.create(post=self.post, ip_address=ip_address, user=user)
            self.views += 1
            self.save()
            return True
        return False

    def increment_metric(self, metric_name):
        """
        Incrementa cualquier métrica específica (likes, comments, shares).
        """
        if hasattr(self, metric_name):
            setattr(self, metric_name, getattr(self, metric_name) + 1)
            self.save()
        else:
            raise ValueError(f"Metric '{metric_name}' does not exist in PostAnalytics")

    def increment_like(self):
        self.likes += 1
        self.save()

    def increment_comment(self):
        self.comments += 1
        self.save()

    def increment_share(self):
        self.shares += 1
        self.save()


class Heading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="headings")
    title = models.CharField(max_length=255)
    slug = models.CharField(max_length=255)
    level = models.IntegerField(
        choices=(
            (1, "H1"),
            (2, "H2"),
            (3, "H3"),
            (4, "H4"),
            (5, "H5"),
            (6, "H6"),
        )
    )
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


@receiver(post_save, sender=Post)
def create_post_analytics(sender, instance, created, **kwargs):
    if created:
        PostAnalytics.objects.create(post=instance)


@receiver(post_save, sender=Category)
def create_category_analytics(sender, instance, created, **kwargs):
    if created:
        CategoryAnalytics.objects.create(category=instance)


""" @receiver(post_save, sender=Comment)
def create_category_analytics(sender, instance, created, **kwargs):
    if created:
        PostInteraction.objects.create(
            user=instance.user,
            post=instance.post,
            interaction_type="comment",
            comment=instance,
            weight=2.0,
        )
        analytics, _ = PostAnalytics.objects.get_or_create(post=instance.post)
        analytics.increment_comment()


@receiver(post_save, sender=Comment)
def handle_post_comment(sender, instance, created, **kwargs):
    if created:
        PostInteraction.objects.create(
            user=instance.user, post=instance.post, interaction_type="comment"
        )
        analytics, _ = PostAnalytics.objects.get_or_create(post=instance.post)
        analytics.increment_comment() """


""" @receiver(post_save, sender=PostView)
def handle_post_view(sender, instance, created, **kwargs):
    if created:
        PostInteraction.objects.create(
            user=instance.user,
            post=instance.post,
            interaction_type="view",
            ip_address=instance.ip_address,
        )
        analytics, _ = PostAnalytics.objects.get_or_create(post=instance.post)
        analytics.increment_metric('views') """


""" @receiver(post_save, sender=PostLike)
def handle_post_like(sender, instance, created, **kwargs):
    if created:
        PostInteraction.objects.create(
            user=instance.user,
            post=instance.post,
            interaction_type="like",
        )
        analytics, _ = PostAnalytics.objects.get_or_create(post=instance.post)
        analytics.increment_like()


@receiver(post_save, sender=PostShare)
def handle_post_share(sender, instance, created, **kwargs):
    if created:
        PostInteraction.objects.create(
            user=instance.user,
            post=instance.post,
            interaction_type="share",
        )
        analytics, _ = PostAnalytics.objects.get_or_create(post=instance.post)
        analytics.increment_share()
 """
