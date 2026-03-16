from django.shortcuts import render
from rest_framework.generics import ListAPIView, RetrieveAPIView, GenericAPIView
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, APIException
import redis
from django.conf import settings
from django.db.models import Q, F, Prefetch
from .models import Post, Heading, PostView, PostAnalytics, Category, CategoryAnalytics
from .serializers import  CategorySerializer,CategoryListSerializer, PostListSerializer, PostSerializer, HeadingSerializer
from .utils import get_client_ip
from .tasks import increment_post_impressions, increment_post_view_task, increment_category_view_task
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


# class PostListView(ListAPIView):
    #queryset = Post.postobjects.all()
    #serializer_class= PostListSerializer

class PostListView(GenericAPIView):
    permission_classes = [HasValidAPIKey]
    pagination_class = Pagination  
    #@method_decorator(cache_page(60*1)) # 1 minute, pero para las analiticas no es tan exacto
    
    def get(self, request, *args, **kwargs):
        try:
            search = request.query_params.get("search", "").strip()
            sorting = request.query_params.get("sorting", None)
            ordering = request.query_params.get("ordering", None)
            categories = request.query_params.getlist("category", [])
            page_number = request.query_params.get("p", "1")
            
            #Manual cache
            cache_key=f"post_list:{search}:{sorting}:{ordering}:{categories}:{page_number}"
            cached_posts = cache.get(cache_key) # verify if data is in cache 
            
            if cached_posts:
                #serialized_posts = PostListSerializer(cached_posts, many=True).data
                
                for post in cached_posts['results']: # Increment impressions on Redis for cached posts
                    redis_client.incr(f"post:impressions:{post['id']}")
                return Response(cached_posts)
            
            posts = Post.postobjects.all().select_related("category").prefetch_related("post_analytics")
            
            # Search param
            if search != "":
                posts = posts.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(keywords__icontains=search) 
                )
            
            # Category filter
            if categories:
                category_queries = Q()
                for category in categories:
                    try:
                        uuid.UUID(category)
                        uuid_query = (
                            Q(category__id=category)
                        )
                        category_queries |= uuid_query
                    except ValueError:
                        slug_query = (
                            Q(category__slug=category)
                        )
                        category_queries |= slug_query
                posts = posts.filter(category_queries).distinct() 
            
            if not posts.exists():
                raise NotFound(detail="No posts found")
            
            # Sorting param
            if sorting:
                if sorting == 'newest':
                    posts = posts.order_by('-created_at')
                elif sorting == 'recently-updated':
                    posts = posts.order_by('-updated_at')
                elif sorting == 'most-viewed':
                    posts = posts.annotate(popularity=F("post_analytics__views")).order_by("-popularity")
            
            # Ordering
            if ordering:
                if ordering == 'az':
                    posts = posts.order_by("title")
                elif ordering == 'za':
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
                
    
    
#class PostDetailView(RetrieveAPIView):
    #queryset = Post.postobjects.all()
    #serializer_class= PostSerializer
    #lookup_field = 'slug'
    
class PostDetailView(RetrieveAPIView):
    permission_classes = [HasValidAPIKey]

    def get(self, request, slug):
        ip_address = get_client_ip(request)

        try:
            cache_key = f"post_detail:{slug}"
            cached_post = cache.get(cache_key)

            if cached_post:
                increment_post_view_task.delay(cached_post["slug"], ip_address)
                return Response(cached_post)

            post = Post.postobjects.get(slug=slug)

            serialized_post = PostSerializer(post).data

            cache.set(cache_key, serialized_post, timeout=60 * 1)

            increment_post_view_task.delay(post.slug, ip_address)

        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")

        except Exception as e:
            raise APIException(detail=f"An unexpected error occurred: {str(e)}")

        return Response(serialized_post)
    
    

class PostHeadingView(ListAPIView):
    permission_classes = [HasValidAPIKey]
    serializer_class= HeadingSerializer
    
    def get_queryset(self):
        post_slug = self.kwargs.get("slug")
        return Heading.objects.filter(post__slug = post_slug)
    
    
class IncrementPostClickView(APIView):
    permission_classes = [HasValidAPIKey]
    
    def post(self, request):
        """Increments the click counter relative to his slug"""
        data = request.data

        try:
            post = Post.postobjects.get(slug=data['slug'])
        except Post.DoesNotExist:
            raise NotFound(detail="The requested post does not exist")
        
        try:
            post_analytics, created = PostAnalytics.objects.get_or_create(post=post)
            post_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics: {str(e)}")

        return Response({
            "message": "Click incremented successfully",
            "clicks": post_analytics.clicks
        })
        
        
class CategoryListView(GenericAPIView): 
    permission_classes = [HasValidAPIKey]
    pagination_class = Pagination 
    
    def get(self, request):
        try:
           
            parent_id = request.query_params.get("parent_id", None)
            search = request.query_params.get("search", "").strip()
            ordering = request.query_params.get("ordering", None)
            page_number = request.query_params.get("p", "1")
            
            cache_key = f"category_list:{parent_id}:{search}:{ordering}:{page_number}"
            cached_categories = cache.get(cache_key)
            
            if cached_categories:
                for category in cached_categories['results']:
                    redis_client.incr(f"category:impressions:{category['id']}")
                return Response(cached_categories)
            if parent_id:
                categories = Category.objects.filter(parent__id=parent_id).select_related("parent").prefetch_related("category_analytics")
            else:
                categories = Category.objects.filter(parent__isnull=True).select_related("parent").prefetch_related("category_analytics")
            
            if search != "":
                categories = categories.filter(
                    Q(name__icontains=search) |
                    Q(title__icontains=search) 
                )
            
            if not categories.exists():
                raise NotFound(detail="No categories found")
            
            if ordering:
                if ordering == 'az':
                    categories = categories.order_by("name")
                elif ordering == 'za':
                    categories = categories.order_by("-name")  
            
            page = self.paginate_queryset(categories)
            if page is not None:
                serialized_categories = CategoryListSerializer(page, many=True).data
                paginated_response = self.get_paginated_response(serialized_categories)
                cache.set(cache_key, paginated_response.data, timeout=60 * 1)
                for category in page:
                    redis_client.incr(f"category:impressions:{category.id}")
                return paginated_response
                
        except NotFound:
            raise
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
            category = Category.objects.get(slug=data['slug'])
        except Category.DoesNotExist:
            raise NotFound(detail="The requested category does not exist")
        
        try:
            category_analytics, _ = CategoryAnalytics.objects.get_or_create(category=category)
            category_analytics.increment_click()
        except Exception as e:
            raise APIException(detail=f"An error ocurred while updating post analytics: {str(e)}")

        return Response({
            "message": "Click incremented successfully",
            "clicks": category_analytics.clicks
        })
        
               
        
class GenerateFakePostsView(APIView):
    def get(self, request):
        fake = Faker()
        categories = list(Category.objects.all())
        
        posts_to_generate = 40
        status_options = ["draft", "published"]
        
        for _ in range(posts_to_generate):
            title = fake.sentence(nb_words=6)
            post = Post(
                id=uuid.uuid4(),
                title=title,
                description=fake.sentence(nb_words=12),
                content=fake.paragraph(nb_sentences=5),
                keywords=", ".join(fake.words(nb=5)),
                slug=slugify(title),
                category=random.choice(categories),
                status=random.choice(status_options),
            )
            post.save()
        return Response({"message": f"{posts_to_generate} posts generated successfully"})
    
class GenerateFakeAnalyticsView(APIView):
    def get(self, request):
        fake = Faker()
        posts = Post.objects.all()
        if not posts: 
            return Response({"error": "There are no posts to generate analytics"}, status=400)
        
        analytics_to_generate = len(posts)
        
        # Generar analíticas para cada post
        for post in posts:
            views = random.randint(50, 1000)  # Número aleatorio de vistas
            impressions = views + random.randint(100, 2000)  # Impresiones >= vistas
            clicks = random.randint(0, views)  # Los clics son <= vistas
            avg_time_on_page = round(random.uniform(10, 300), 2)  # Tiempo promedio en segundos
            
            # Crear o actualizar analíticas para el post
            analytics, created = PostAnalytics.objects.get_or_create(post=post)
            analytics.views = views
            analytics.impressions = impressions
            analytics.clicks = clicks
            analytics.avg_time_on_page = avg_time_on_page
            analytics._update_click_through_rate()  # Recalcular el CTR
            analytics.save()

        return Response({"message": f"Analíticas generadas para {analytics_to_generate} posts."})