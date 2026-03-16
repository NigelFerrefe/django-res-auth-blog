import uuid
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from tinymce.models import HTMLField
from .utils import get_client_ip

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
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_view')
    ip_address =models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    


class CategoryAnalytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.OneToOneField(Category, on_delete=models.CASCADE, related_name='category_analytics')
    views = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    click_through_rate = models.FloatField(default=0) # Promedio de clicks por vistas
    avg_time_on_page = models.FloatField(default=0) # Cuanto tiempo pasa una persona leyendo el post
    
    
    def _update_click_through_rate(self):
        if self.impressions > 0:
            self.click_through_rate = (self.clicks/self.impressions) * 100
        else:
            self.click_through_rate = 0
        self.save()
            
    def increment_click(self):
        self.clicks += 1
        self.save()
        self._update_click_through_rate()
        
    def increment_impression(self):
        self.impressions +=1
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
    title = models.CharField(max_length=128)
    description = models.CharField(max_length=256)
    content = HTMLField()
    thumbnail = models.ImageField(upload_to=blog_thumbnail_directory)
    keywords = models.CharField(max_length=128)
    slug = models.CharField(max_length=128)
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

# Analytic to keep track about how many times your post has been visited
class PostView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='post_view')
    ip_address =models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['post', 'ip_address'],
                name='unique_post_ip_view'
            )
        ]


# Analytic to get post recommendations
class PostAnalytics(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='post_analytics')
    views = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    click_through_rate = models.FloatField(default=0) # Promedio de clicks por vistas
    avg_time_on_page = models.FloatField(default=0) # Cuanto tiempo pasa una persona leyendo el post
    
    
    def _update_click_through_rate(self):
        if self.impressions > 0:
            self.click_through_rate = (self.clicks/self.impressions) * 100
        else:
            self.click_through_rate = 0
        self.save()
            
    def increment_click(self):
        self.clicks += 1
        self.save()
        self._update_click_through_rate()
        
    def increment_impression(self):
        self.impressions +=1
        self.save()
        self._update_click_through_rate()
        
    def increment_view(self, ip_address):
        try:
            PostView.objects.create(post=self.post, ip_address=ip_address)
            self.views += 1
            self.save()
        except Exception:
            pass



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