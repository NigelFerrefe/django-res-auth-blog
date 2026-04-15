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
    IncrementCategoryClickView,
    PostCommentViews,
    ListPostCommentsView,
    ListCommentRepliesView,
    CommentReplyViews,
    PostLikeViews,
    PostShareView,
    PostAuthorViews,
    PostAuthorDetailView,
    CategoryListAllView,
)


urlpatterns = [
    path("generate_posts/", GenerateFakePostsView.as_view()),
    path("generate_analytics/", GenerateFakeAnalyticsView.as_view()),
    path("posts/", PostListView.as_view(), name="post-list"),
    path("posts/comment/", PostCommentViews.as_view(), name="post-comment"),
    path("posts/comments/", ListPostCommentsView.as_view(), name="post-comments"),
    path(
        "posts/comment/reply/", CommentReplyViews.as_view(), name="post-comment-reply"
    ),
    path(
        "posts/comment/replies/",
        ListCommentRepliesView.as_view(),
        name="post-comments-replies",
    ),
    path("post/author/", PostAuthorViews.as_view()),
    path(
        "post/author/detail/", PostAuthorDetailView.as_view(), name="post-author-detail"
    ),
    path("post/headings/", PostHeadingView.as_view(), name="post-headings"),
    path(
        "post/increment_clicks/",
        IncrementPostClickView.as_view(),
        name="post-increment-click",
    ),
    path("post/<slug:slug>/like/", PostLikeViews.as_view()),
    path("post/<slug:slug>/share/", PostShareView.as_view()),
    path("post/<slug>/", PostDetailView.as_view(), name="post-detail"),
    path(
        "category/increment_clicks/",
        IncrementCategoryClickView.as_view(),
        name="category-increment-click",
    ),
    path("categories", CategoryListView.as_view(), name="category-list"),
    path("categories/list/", CategoryListAllView.as_view(), name="category-list"),
    path("categories/<slug>/", CategoryDetailView.as_view(), name="category-detail"),
]
