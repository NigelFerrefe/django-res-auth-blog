from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'profile_picture_preview', 'birthday', 'linkedin')
    search_fields = ('user__username', 'user__email', 'bio', 'linkedin')
    list_filter = ('birthday',)
    readonly_fields = ('profile_picture_preview', 'banner_picture_preview')
    ordering = ('user__username',)
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'birthday', 'bio')
        }),
        ('Profile Pictures', {
            'fields': ('profile_picture', 'banner_picture')
        }),
        ('Social Links', {
            'fields': ('linkedin', 'instagram')
        }),
    )