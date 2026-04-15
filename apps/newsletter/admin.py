from django.contrib import admin
from .models import ContactMessage, NewsletterUser

class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number', 'created_at')
    list_filter = ('created_at', 'email')
    search_fields = ('first_name', 'last_name', 'email', 'phone_number', 'message')
    date_hierarchy = 'created_at'
    fields = ('first_name', 'last_name', 'email', 'phone_number', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

class NewsletterUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'date_added')
    search_fields = ('email',)
    date_hierarchy = 'date_added'
    ordering = ('-date_added',)
    readonly_fields = ('date_added',)

admin.site.register(ContactMessage, ContactMessageAdmin)
admin.site.register(NewsletterUser, NewsletterUserAdmin)