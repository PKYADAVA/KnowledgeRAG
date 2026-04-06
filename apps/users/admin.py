"""Admin registration for User model."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "display_name", "document_count", "is_active", "created_at")
    list_filter = ("is_active", "is_staff", "created_at")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at", "document_count")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("bio", "avatar", "max_documents", "preferred_language")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
