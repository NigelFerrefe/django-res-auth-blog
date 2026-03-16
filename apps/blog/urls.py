from django.urls import path
from .views import (
    PostListView,
    PostDetailView,
    PostHeadingView,
    IncrementPostClickView,
    GenerateFakeAnalyticsView,
    GenerateFakePostsView,
    CategoryListView,
    CategoryDetailView,
    IncrementCategoryClickView
)


urlpatterns = [
    path("generate_posts/", GenerateFakePostsView.as_view()),
    path("generate_analytics/", GenerateFakeAnalyticsView.as_view()),
    path("posts/", PostListView.as_view(), name="post-list"),
    path("posts/<slug>/", PostDetailView.as_view(), name="post-detail"),
    path("post/headings/", PostHeadingView.as_view(), name="post-headings"),
    path(
        "post/increment_clicks/",
        IncrementPostClickView.as_view(),
        name="post-increment-click",
    ),
    path(
        "category/increment_clicks/",
        IncrementCategoryClickView.as_view(),
        name="category-increment-click",
    ),
    path("categories", CategoryListView.as_view(), name="category-list"),
    path("categories/<slug>/", CategoryDetailView.as_view(), name="category-detail"),
]
