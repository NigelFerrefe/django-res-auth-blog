from django.shortcuts import get_object_or_404, render
from rest_framework.generics import ListAPIView, RetrieveAPIView, GenericAPIView
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework import permissions, status
from rest_framework.response import Response
from django.db import IntegrityError
from rest_framework.exceptions import NotFound, APIException, ValidationError
import redis
from django.conf import settings
from django.db.models import Q, F, Prefetch
from apps.media.models import Media
from utils.string_utils import sanitize_string, sanitize_html
from bs4 import BeautifulSoup
from apps.authentication.models import UserAccount
from .models import (
    Post,
    Heading,
    PostInteraction,
    PostLike,
    PostShare,
    PostView,
    PostAnalytics,
    Category,
    CategoryAnalytics,
    Comment,
)
from .serializers import (
    CategorySerializer,
    CategoryListSerializer,
    PostListSerializer,
    PostSerializer,
    HeadingSerializer,
    CommentSerializer,
    PostAuthorDetailSerializer,
)
from .utils import get_client_ip
from .tasks import (
    increment_post_impressions,
    increment_post_view_task,
    increment_category_view_task,
)
from .pagination import Pagination
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from core.permissions import HasValidAPIKey
from django.core.cache import cache
from faker import Faker
import random
import uuid
from django.utils.text import slugify

redis_client = redis.StrictRedis(host=settings.REDIS_HOST, port=6379, db=0)


class CategoryListAllView(APIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request):
        categories = Category.objects.all()
        serialized = CategoryListSerializer(categories, many=True).data
        return Response(serialized)


class PostAuthorDetailView(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def get(self, request):
        """Obtener un post del autor autenticado para edición"""
        user = request.user

        if user.role == "customer":
            return Response(
                {"error": "You do not have permission to view posts"},
                status=403,
            )

        post_slug = request.query_params.get("slug")
        if not post_slug:
            return Response(
                {"error": "Slug parameter is required"},
                status=400,
            )

        post = Post.objects.filter(slug=post_slug, user=user).first()
        if not post:
            return Response(
                {"error": "Post not found or you do not have permission to access it"},
                status=404,
            )

        serialized_post = PostAuthorDetailSerializer(
            post, context={"request": request}
        ).data

        return Response(serialized_post, status=200)


class PostAuthorViews(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]
    pagination_class = Pagination

    def get(self, request):
        """Enlistar los posts del autor paginados"""
        user = request.user
        if user.role == "customer":
            return Response(
                {"error": "You do not have permission to create posts"}, status=403
            )

        posts = Post.objects.filter(user=user)

        paginator = self.pagination_class()
        paginated_posts = paginator.paginate_queryset(posts, request)
        serialized_posts = PostListSerializer(paginated_posts, many=True).data

        return paginator.get_paginated_response(serialized_posts)

    def post(self, request):
        """Crear un post para un autor"""
        user = request.user
        if user.role == "customer":
            return Response(
                {"error": "You do not have permission to create posts"}, status=403
            )

        required_fields = ["title", "content", "slug", "category"]
        missing_fields = [f for f in required_fields if not request.data.get(f)]
        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=400,
            )

        title = sanitize_string(request.data.get("title"))
        description = sanitize_string(request.data.get("description", ""))
        content = sanitize_html(request.data.get("content"))
        post_status = sanitize_string(request.data.get("status", "draft"))
        keywords = sanitize_string(request.data.get("keywords", ""))
        slug = slugify(request.data.get("slug"))
        category_slug = slugify(request.data.get("category"))

        category = get_object_or_404(Category, slug=category_slug)

        try:
            soup = BeautifulSoup(content, "html.parser")
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

            post = Post.objects.create(
                user=user,
                title=title,
                description=description,
                content=str(soup),
                keywords=keywords,
                slug=slug,
                category=category,
                status=post_status,
            )

            PostAnalytics.objects.create(post=post)

            thumbnail_key = request.data.get("thumbnail_key")
            if thumbnail_key:
                thumbnail = Media.objects.create(
                    order=request.data.get("thumbnail_order", 0),
                    name=request.data.get("thumbnail_name"),
                    size=request.data.get("thumbnail_size"),
                    type=request.data.get("thumbnail_type"),
                    key=thumbnail_key,
                    media_type=request.data.get("thumbnail_media_type", "image"),
                )
                post.thumbnail = thumbnail

            for order, heading in enumerate(headings, start=1):
                text = heading.get_text(strip=True)
                heading_slug = slugify(text)
                level = int(heading.name[1])

                heading["id"] = heading_slug

                Heading.objects.create(
                    post=post,
                    title=text,
                    slug=heading_slug,
                    level=level,
                    order=order,
                )

            post.content = str(soup)
            post.save()

        except IntegrityError:
            return Response(
                {"error": "A post with this slug already exists."},
                status=400,
            )

        except Exception:
            return Response(
                {"error": "An unexpected error occurred while creating the post."},
                status=500,
            )

        return Response(
            {"message": f"Post '{post.title}' created successfully."},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request):
        """Actualizar un post"""
        user = request.user
        if user.role == "customer":
            return Response(
                {"error": "You do not have permission to edit posts"}, status=403
            )

        post_slug = request.data.get("post_slug")
        post = get_object_or_404(Post, slug=post_slug, user=user)
        old_slug = post.slug

        post.title = sanitize_string(request.data.get("title", post.title))
        post.description = sanitize_string(
            request.data.get("description", post.description)
        )
        post.content = sanitize_html(request.data.get("content", post.content))
        post.status = sanitize_string(request.data.get("status", post.status))
        post.keywords = sanitize_string(request.data.get("keywords", post.keywords))
        new_slug = slugify(request.data.get("slug", post.slug))

        if Post.objects.filter(slug=new_slug).exclude(id=post.id).exists():
            return Response(
                {"error": f"The slug '{new_slug}' is already in use"}, status=400
            )
        post.slug = new_slug

        category_slug = slugify(request.data.get("category", post.category.slug))
        post.category = get_object_or_404(Category, slug=category_slug)

        thumbnail_key = request.data.get("thumbnail_key")
        if thumbnail_key:
            thumbnail = Media.objects.create(
                order=request.data.get("thumbnail_order", 0),
                name=request.data.get("thumbnail_name"),
                size=request.data.get("thumbnail_size"),
                type=request.data.get("thumbnail_type"),
                key=thumbnail_key,
                media_type=request.data.get("thumbnail_media_type", "image"),
            )
            post.thumbnail = thumbnail

        soup = BeautifulSoup(post.content, "html.parser")
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        Heading.objects.filter(post=post).delete()

        for order, heading in enumerate(headings, start=1):
            text = heading.get_text(strip=True)
            heading_slug = slugify(text)
            level = int(heading.name[1])

            heading["id"] = heading_slug

            Heading.objects.create(
                post=post,
                title=text,
                slug=heading_slug,
                level=level,
                order=order,
            )

        post.content = str(soup)
        post.save()

        cache.delete(f"post_detail:{old_slug}")
        cache.delete(f"post_detail:{post.slug}")

        cache_keys = cache.keys("post_list:*")
        for key in cache_keys:
            cache.delete(key)

        serialized_post = PostSerializer(post, context={"request": request}).data
        return Response(serialized_post, status=200)

    def delete(self, request):
        """Borrar un post"""
        user = request.user
        if user.role == "customer":
            return Response(
                {"error": "You do not have permission to delete posts"}, status=403
            )

        post_slug = request.query_params.get("slug")
        post = get_object_or_404(Post, slug=post_slug, user=user)
        post.delete()

        # Invalidar caché
        cache.delete(f"post_detail:{post_slug}")
        cache_keys = cache.keys("post_list:*")
        for key in cache_keys:
            cache.delete(key)

        return Response(
            {"message": f"Post '{post_slug}' deleted successfully"}, status=200
        )


class PostListView(GenericAPIView):
    permission_classes = [HasValidAPIKey]
    pagination_class = Pagination
    # @method_decorator(cache_page(60*1)) # 1 minute, pero para las analiticas no es tan exacto

    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "").strip()
            sorting = request.query_params.get("sorting", None)
            ordering = request.query_params.get("ordering", None)
            author = request.query_params.get("author", None)
            categories = request.query_params.getlist("category", [])
            page_number = request.query_params.get("p", "1")
            is_featured = request.query_params.get("is_featured", None)

            # Manual cache
            cache_key = f"post_list:{search}:{sorting}:{ordering}:{author}:{categories}:{page_number}:{is_featured}"
            cached_posts = cache.get(cache_key)  # verify if data is in cache

            if cached_posts:
                # serialized_posts = PostListSerializer(cached_posts, many=True).data

                for post in cached_posts[
                    "results"
                ]:  # Increment impressions on Redis for cached posts
                    redis_client.incr(f"post:impressions:{post['id']}")
                return Response(cached_posts)

            posts = (
                Post.postobjects.all()
                .select_related("category")
                .prefetch_related("post_analytics")
            )

            # Search param
            if search != "":
                posts = posts.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                    | Q(keywords__icontains=search)
                )

            # Filter by Author
            if author:
                posts = posts.filter(user__username=author)

            # Category filter
            if categories:
                category_queries = Q()
                for category in categories:
                    try:
                        uuid.UUID(category)
                        uuid_query = Q(category__id=category)
                        category_queries |= uuid_query
                    except ValueError:
                        slug_query = Q(category__slug=category)
                        category_queries |= slug_query
                posts = posts.filter(category_queries).distinct()

            if is_featured is not None:
                is_featured = is_featured.lower() in ["true", "1", "yes"]
                posts = posts.filter(featured=is_featured)

            # Sorting param
            if sorting:
                if sorting == "newest":
                    posts = posts.order_by("-created_at")
                elif sorting == "recently-updated":
                    posts = posts.order_by("-updated_at")
                elif sorting == "most-viewed":
                    posts = posts.annotate(
                        popularity=F("post_analytics__views")
                    ).order_by("-popularity")

            # Ordering
            if ordering:
                if ordering == "az":
                    posts = posts.order_by("title")
                elif ordering == "za":
                    posts = posts.order_by("-title")

            # Pagination
            page = self.paginate_queryset(posts)
            if page is not None:
                serialized_posts = PostListSerializer(page, many=True).data
                paginated_response = self.get_paginated_response(serialized_posts)
                cache.set(cache_key, paginated_response.data, timeout=60 * 1)
                for post in page:
                    redis_client.incr(f"post:impressions:{post.id}")
                return paginated_response

        except NotFound:
            raise
        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")


# class PostDetailView(RetrieveAPIView):
# queryset = Post.postobjects.all()
# serializer_class= PostSerializer
# lookup_field = 'slug'


class PostDetailView(RetrieveAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, slug):
        ip_address = get_client_ip(request)
        user = request.user if request.user.is_authenticated else None

        try:
            cache_key = f"post_detail:{slug}"
            cached_post = cache.get(cache_key)

            # ✅ Si está en cache
            if cached_post:
                serialized_post = PostSerializer(
                    cached_post, context={"request": request}
                ).data

                self._register_view_interaction(cached_post, ip_address, user)
                return Response(serialized_post)

            # ✅ Si no está en cache
            post = Post.postobjects.get(slug=slug)

            serialized_post = PostSerializer(post, context={"request": request}).data

            # 🔥 Guardamos el objeto (no el JSON)
            cache.set(cache_key, post, timeout=60 * 5)

            self._register_view_interaction(post, ip_address, user)

        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")

        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")

        return Response(serialized_post)

    def _register_view_interaction(self, post, ip_address, user):
        """
        Registra una vista única y actualiza analytics.
        - Usuario autenticado → 1 vista por usuario/post
        - Usuario anónimo → 1 vista por IP/post
        """

        if user:
            view, created = PostView.objects.get_or_create(
                post=post, user=user, defaults={"ip_address": ip_address}
            )
        else:
            view, created = PostView.objects.get_or_create(
                post=post, ip_address=ip_address, defaults={"user": None}
            )

        # Si era anónimo y ahora hay user → lo actualizamos
        if not created and user and view.user is None:
            view.user = user
            view.save(update_fields=["user"])

        # Solo si es nueva vista → analytics
        if created:
            PostInteraction.objects.create(
                user=user,
                post=post,
                interaction_type="view",
                ip_address=ip_address,
            )

            analytics, _ = PostAnalytics.objects.get_or_create(post=post)
            analytics.increment_metric("views")


"""     def _register_view_interaction(self, post, ip_address, user):
        view, created = PostView.objects.get_or_create(
            post=post,
            ip_address=ip_address,
            defaults={"user": user}
        )

        # Si ya existía la vista pero ahora hay un user autenticado, actualizarlo
        if not created and user and view.user is None:
            view.user = user
            view.save(update_fields=["user"])

        if created:
            # Solo crear interacción y actualizar métricas si es nueva
            PostInteraction.objects.create(
                user=user,
                post=post,
                interaction_type="view",
                ip_address=ip_address,
            )

            analytics, _ = PostAnalytics.objects.get_or_create(post=post)
            analytics.increment_metric("views") """


class PostHeadingView(ListAPIView):
    permission_classes = [HasValidAPIKey]
    serializer_class = HeadingSerializer

    def get_queryset(self):
        post_slug = self.kwargs.get("slug")
        return Heading.objects.filter(post__slug=post_slug)


class IncrementPostClickView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """Increments the click counter relative to his slug"""
        data = request.data

        try:
            post = Post.postobjects.get(slug=data["slug"])
        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")

        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_click()
        except Exception as e:
            raise APIException(
                detail=f"An error ocurred while updating post analytics: {str(e)}"
            )

        return Response(
            {
                "message": "Click incremented successfully",
                "clicks": post_analytics.clicks,
            }
        )


class CategoryListView(GenericAPIView):
    permission_classes = [HasValidAPIKey]
    pagination_class = Pagination

    def get(self, request):
        try:
            parent_slug = request.query_params.get("parent_slug", None)
            search = request.query_params.get("search", "").strip()
            ordering = request.query_params.get("ordering", None)
            page_number = request.query_params.get("p", "1")

            cache_key = f"category_list:{parent_slug}:{search}:{ordering}:{page_number}"
            cached_categories = cache.get(cache_key)

            if cached_categories is not None:
                for category in cached_categories.get("results", []):
                    redis_client.incr(f"category:impressions:{category['id']}")
                return Response(cached_categories)

            if parent_slug:
                categories = (
                    Category.objects.filter(parent__slug=parent_slug)
                    .select_related("parent")
                    .prefetch_related("category_analytics")
                )
            else:
                categories = (
                    Category.objects.filter(parent__isnull=True)
                    .select_related("parent")
                    .prefetch_related("category_analytics")
                )

            if search:
                categories = categories.filter(
                    Q(name__icontains=search) | Q(title__icontains=search)
                )

            if ordering == "az":
                categories = categories.order_by("name")
            elif ordering == "za":
                categories = categories.order_by("-name")

            page = self.paginate_queryset(categories)
            serialized_categories = CategoryListSerializer(page, many=True).data
            paginated_response = self.get_paginated_response(serialized_categories)

            cache.set(cache_key, paginated_response.data, timeout=60)

            for category in page:
                redis_client.incr(f"category:impressions:{category.id}")

            return paginated_response

        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")


class CategoryDetailView(RetrieveAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, slug):
        ip_address = get_client_ip(request)

        try:
            cache_key = f"category_detail:{slug}"
            cached_category = cache.get(cache_key)

            if cached_category:
                increment_category_view_task.delay(cached_category["slug"], ip_address)
                return Response(cached_category)

            category = Category.objects.get(slug=slug)

            serialized_categories = CategorySerializer(category).data

            cache.set(cache_key, serialized_categories, timeout=60 * 1)

            increment_category_view_task.delay(category.slug, ip_address)

        except Category.DoesNotExist:
            raise NotFound(detail="The requested category does not exist")

        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")

        return Response(serialized_categories)


class IncrementCategoryClickView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request):
        """Increments the click counter relative to his slug"""
        data = request.data

        try:
            category = Category.objects.get(slug=data["slug"])
        except Category.DoesNotExist:
            raise NotFound(detail="The requested category does not exist")

        try:
            category_analytics, _ = CategoryAnalytics.objects.get_or_create(
                category=category
            )
            category_analytics.increment_click()
        except Exception as e:
            raise APIException(
                detail=f"An error ocurred while updating post analytics: {str(e)}"
            )

        return Response(
            {
                "message": "Click incremented successfully",
                "clicks": category_analytics.clicks,
            }
        )


class ListPostCommentsView(APIView):
    permission_classes = [HasValidAPIKey]
    pagination_class = Pagination

    def get(self, request):
        post_slug = request.query_params.get("slug", None)
        page = request.query_params.get("p", "1")

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")

        # Cache por slug + página
        cache_key = f"post_comments:{post_slug}:{page}"
        cached_comments = cache.get(cache_key)
        if cached_comments:
            return Response(cached_comments, status=status.HTTP_200_OK)

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")

        comments = (
            Comment.objects.filter(post=post, parent=None, is_active=True)
            .select_related("user")
            .order_by("-created_at")
        )

        paginator = self.pagination_class()
        paginated_comments = paginator.paginate_queryset(comments, request)
        serialized_comments = CommentSerializer(paginated_comments, many=True).data

        response = paginator.get_paginated_response(serialized_comments)

        # Guardar índice de cache
        cache_index_key = f"post_comments_cache_keys:{post_slug}"
        cache_keys = cache.get(cache_index_key, [])

        if cache_key not in cache_keys:
            cache_keys.append(cache_key)

        cache.set(cache_index_key, cache_keys, timeout=60 * 5)

        # Guardar respuesta completa (IMPORTANTE)
        cache.set(cache_key, response.data, timeout=60 * 5)

        return response


class PostCommentViews(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):
        post_slug = request.data.get("slug", None)
        user = request.user
        ip_address = get_client_ip(request)
        content = sanitize_html(request.data.get("content", None))

        if not post_slug:
            raise NotFound(detail="A valid post slug must be provided")

        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            raise NotFound(detail=f"Post: {post_slug} does not exist")

        comment = Comment.objects.create(user=user, post=post, content=content)

        self._invalidate_post_comments_cache(post_slug)
        self._register_comment_interaction(comment, post, ip_address, user)

        return Response(
            {"message": f"Comment created for post {post.title}"},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request):
        comment_id = request.data.get("comment_id", None)
        content = sanitize_html(request.data.get("content", None))

        if not comment_id:
            raise NotFound(detail="A valid comment id must be provided")

        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id: {comment_id} does not exist")

        comment.content = content
        comment.save()

        self._invalidate_post_comments_cache(comment.post.slug)

        if comment.parent and comment.parent.replies.exists():
            self._invalidate_comment_replies_cache(comment.parent.id)

        return Response(
            {"message": "Comment content updated successfully"},
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        comment_id = request.query_params.get("comment_id", None)

        if not comment_id:
            raise NotFound(detail="A valid comment id must be provided")

        try:
            comment = Comment.objects.get(id=comment_id, user=request.user)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id: {comment_id} does not exist")

        post = comment.post
        post_analytics, _ = PostAnalytics.objects.get_or_create(post=post)

        if comment.parent and comment.parent.replies.exists():
            self._invalidate_comment_replies_cache(comment.parent.id)

        comment.delete()

        comments_count = Comment.objects.filter(post=post, is_active=True).count()
        post_analytics.comments = comments_count
        post_analytics.save()

        self._invalidate_post_comments_cache(post.slug)

        return Response(
            {"message": "Comment deleted successfully"}, status=status.HTTP_200_OK
        )

    def _register_comment_interaction(self, comment, post, ip_address, user):
        _, created = PostInteraction.objects.get_or_create(
            user=user,
            post=post,
            interaction_type="comment",
            comment=comment,
            defaults={"ip_address": ip_address},
        )
        if created:
            analytics, _ = PostAnalytics.objects.get_or_create(post=post)
            analytics.increment_metric("comments")

    def _invalidate_post_comments_cache(self, post_slug):
        cache_index_key = f"post_comments_cache_keys:{post_slug}"
        cache_keys = cache.get(cache_index_key, [])
        for key in cache_keys:
            cache.delete(key)
        cache.delete(cache_index_key)

    def _invalidate_comment_replies_cache(self, comment_id):
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])
        for key in cache_keys:
            cache.delete(key)
        cache.delete(cache_index_key)


class ListCommentRepliesView(APIView):
    permission_classes = [HasValidAPIKey]
    pagination_class = Pagination

    def get(self, request):
        comment_id = request.query_params.get("comment_id")
        page = request.query_params.get("p", "1")

        if not comment_id:
            raise NotFound(detail="A valid comment_id must be provided")

        cache_key = f"comment_replies:{comment_id}:{page}"
        cached_replies = cache.get(cache_key)
        if cached_replies:
            return Response(cached_replies, status=status.HTTP_200_OK)

        try:
            parent_comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id: {comment_id} does not exist")

        replies = parent_comment.replies.filter(is_active=True).order_by("-created_at")
        serialized_replies = CommentSerializer(replies, many=True).data

        paginator = Pagination()
        paginated_replies = paginator.paginate_queryset(replies, request)
        serialized_replies = CommentSerializer(paginated_replies, many=True).data

        self._register_comment_reply_cache_key(comment_id, cache_key)
        cache.set(cache_key, serialized_replies, timeout=60 * 5)

        return paginator.get_paginated_response(serialized_replies)

    def _register_comment_reply_cache_key(self, comment_id, cache_key):
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])
        if cache_key not in cache_keys:
            cache_keys.append(cache_key)
        cache.set(cache_index_key, cache_keys, timeout=60 * 5)


class CommentReplyViews(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request):
        comment_id = request.data.get("comment_id")
        user = request.user
        ip_address = get_client_ip(request)
        content = sanitize_html(request.data.get("content", None))

        if not comment_id:
            raise NotFound(detail="A valid comment_id must be provided")

        try:
            parent_comment = Comment.objects.get(id=comment_id)
        except Comment.DoesNotExist:
            raise NotFound(detail=f"Comment with id: {comment_id} does not exist")

        comment = Comment.objects.create(
            user=user,
            post=parent_comment.post,
            parent=parent_comment,
            content=content,
        )

        self._invalidate_comment_replies_cache(comment_id)
        self._register_comment_interaction(comment, comment.post, ip_address, user)

        return Response(
            {"message": "Comment reply created successfully"},
            status=status.HTTP_201_CREATED,
        )

    def _register_comment_interaction(self, comment, post, ip_address, user):
        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type="comment",
            comment=comment,
            ip_address=ip_address,
        )
        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.increment_metric("comments")

    def _invalidate_comment_replies_cache(self, comment_id):
        cache_index_key = f"comment_replies_cache_keys:{comment_id}"
        cache_keys = cache.get(cache_index_key, [])
        for key in cache_keys:
            cache.delete(key)
        cache.delete(cache_index_key)


class PostLikeViews(APIView):
    permission_classes = [HasValidAPIKey, permissions.IsAuthenticated]

    def post(self, request, slug):
        user = request.user
        post = get_object_or_404(Post, slug=slug)

        PostLike.objects.get_or_create(post=post, user=user)

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.likes = PostLike.objects.filter(post=post).count()
        analytics.save()

        return Response(
            {
                "liked": True,
                "likes_count": analytics.likes,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, slug):
        user = request.user
        post = get_object_or_404(Post, slug=slug)

        PostLike.objects.filter(post=post, user=user).delete()

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.likes = PostLike.objects.filter(post=post).count()
        analytics.save()

        return Response(
            {
                "liked": False,
                "likes_count": analytics.likes,
            },
            status=status.HTTP_200_OK,
        )


class PostShareView(APIView):
    permission_classes = [HasValidAPIKey]

    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug)
        platform = request.data.get("platform", "other").lower()
        user = request.user if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        valid_platforms = [
            choice[0] for choice in PostShare._meta.get_field("platform").choices
        ]
        if platform not in valid_platforms:
            raise ValidationError(
                detail=f"Invalid platform. Valid options are: {', '.join(valid_platforms)}"
            )

        PostShare.objects.create(post=post, user=user, platform=platform)

        PostInteraction.objects.create(
            user=user,
            post=post,
            interaction_type="share",
            ip_address=ip_address,
        )

        analytics, _ = PostAnalytics.objects.get_or_create(post=post)
        analytics.shares = PostShare.objects.filter(post=post).count()
        analytics.save()

        return Response(
            {
                "shared": True,
                "shares_count": analytics.shares,
                "platform": platform,
            },
            status=status.HTTP_200_OK,
        )


class GenerateFakePostsView(APIView):
    def get(self, request):
        fake = Faker()
        categories = list(Category.objects.all())

        posts_to_generate = 40
        status_options = ["draft", "published"]

        for _ in range(posts_to_generate):
            title = fake.sentence(nb_words=6)
            user = UserAccount.objects.get(username="test_editor")
            post = Post(
                id=uuid.uuid4(),
                user=user,
                title=title,
                description=fake.sentence(nb_words=12),
                content=fake.paragraph(nb_sentences=5),
                keywords=", ".join(fake.words(nb=5)),
                slug=slugify(title),
                category=random.choice(categories),
                status=random.choice(status_options),
            )
            post.save()
        return Response(
            {"message": f"{posts_to_generate} posts generated successfully"}
        )


class GenerateFakeAnalyticsView(APIView):
    def get(self, request):
        fake = Faker()
        posts = Post.objects.all()
        if not posts:
            return Response(
                {"error": "There are no posts to generate analytics"}, status=400
            )

        analytics_to_generate = len(posts)

        # Generar analíticas para cada post
        for post in posts:
            views = random.randint(50, 1000)  # Número aleatorio de vistas
            impressions = views + random.randint(100, 2000)  # Impresiones >= vistas
            clicks = random.randint(0, views)  # Los clics son <= vistas
            avg_time_on_page = round(
                random.uniform(10, 300), 2
            )  # Tiempo promedio en segundos

            # Crear o actualizar analíticas para el post
            analytics, created = PostAnalytics.objects.get_or_create(post=post)
            analytics.views = views
            analytics.impressions = impressions
            analytics.clicks = clicks
            analytics.avg_time_on_page = avg_time_on_page
            analytics._update_click_through_rate()  # Recalcular el CTR
            analytics.save()

        return Response(
            {"message": f"Analíticas generadas para {analytics_to_generate} posts."}
        )
