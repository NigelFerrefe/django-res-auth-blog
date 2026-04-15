from rest_framework import serializers

from apps.media.serializers import MediaSerializer
from apps.authentication.serializers import UserPublicSerializer
from .models import (
    CategoryAnalytics,
    Post,
    Category,
    Heading,
    PostAnalytics,
    PostLike,
    PostShare,
    PostView,
    PostInteraction,
    Comment,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"


class CategoryListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "thumbnail"]


class CategoryAnalyticsSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = CategoryAnalytics
        fields = [
            "id",
            "category_name",
            "views",
            "impressions",
            "clicks",
            "click_through_rate",
            "avg_time_on_page",
        ]

    def get_category_name(self, obj):
        return obj.category.name


class HeadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Heading
        fields = [
            "id",
            "title",
            "slug",
            "level",
            "order",
        ]


class PostViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostView
        fields = "__all__"


class PostSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    headings = HeadingSerializer(many=True)
    view_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    has_liked = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    thumbnail = MediaSerializer()
    user = serializers.StringRelatedField()

    class Meta:
        model = Post
        fields = "__all__"

    def get_view_count(self, obj):
        return obj.post_analytics.views if obj.post_analytics else 0

    def get_comments_count(self, obj):
        return obj.post_comments.filter(parent=None, is_active=True).count()

    def get_likes_count(self, obj):
        return obj.likes.filter().count()

    def get_has_liked(self, obj):
        """
        Verifica si el usuario autenticado ha dado 'like' al post.
        """
        user = self.context.get("request").user
        if user and user.is_authenticated:
            return PostLike.objects.filter(post=obj, user=user).exists()
        return False


class PostInteractionSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()  # Return users email
    post_title = serializers.SerializerMethodField()
    comment_content = serializers.SerializerMethodField()

    class Meta:
        model = PostInteraction
        fields = [
            "id",
            "user",
            "post",
            "post_title",
            "interaction_type",
            "interaction_category",
            "weight",
            "timestamp",
            "ip_address",
            "hour_of_day",
            "day_of_week",
            "comment_content",
        ]

    def get_post_title(self, obj):
        return obj.post.title

    def get_comment_content(self, obj):
        return obj.comment.content if obj.comment else None


class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    post_title = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    # replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "user",
            "post",
            "post_title",
            "parent",
            "content",
            "created_at",
            "updated_at",
            "is_active",
            "replies_count",
            # "replies",
        ]

    def get_post_title(self, obj):
        return obj.post.title

    def get_replies(self, obj):
        replies = obj.replies.filter(is_active=True)
        return CommentSerializer(replies, many=True).data

    def get_replies_count(self, obj):
        return obj.replies.filter(is_active=True).count()


class PostListSerializer(serializers.ModelSerializer):
    category = CategoryListSerializer()
    thumbnail = MediaSerializer()
    view_count = serializers.SerializerMethodField()
    user = UserPublicSerializer()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "description",
            "thumbnail",
            "slug",
            "category",
            "view_count",
            "user",
            "status",
            "created_at",
            "updated_at",
            "user",
            "featured",
        ]


    def get_view_count(self, obj):
        return (
            obj.post_analytics.views
            if hasattr(obj, "post_analytics") and obj.post_analytics
            else 0
        )


class PostAnalyticsSerializer(serializers.ModelSerializer):
    post_title = serializers.SerializerMethodField()

    class Meta:
        model = PostAnalytics
        fields = [
            "id",
            "post_title",
            "impressions",
            "clicks",
            "click_through_rate",
            "avg_time_on_page",
            "views",
            "likes",
            "comments",
            "shares",
        ]

    def get_post_title(self, obj):
        return obj.post.title


class PostLikeSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = PostLike
        fields = [
            "id",
            "post",
            "user",
            "timestamp",
        ]


class PostShareSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = PostShare
        fields = [
            "id",
            "post",
            "user",
            "platform",
            "timestamp",
        ]


class PostAuthorDetailSerializer(serializers.ModelSerializer):
    thumbnail = MediaSerializer()
    category = serializers.SlugRelatedField(read_only=True, slug_field="slug")

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "description",
            "content",
            "thumbnail",
            "keywords",
            "slug",
            "category",
            "status",
            "created_at",
            "updated_at",
        ]
