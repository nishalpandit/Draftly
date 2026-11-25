from django.contrib import admin
from .models import Document, DocumentShare


class DocumentShareInline(admin.TabularInline):
    model = DocumentShare
    extra = 1
    raw_id_fields = ('user',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at', 'updated_at')
    search_fields = ('title', 'content', 'owner__username', 'owner__email')
    list_filter = ('created_at', 'updated_at')
    raw_id_fields = ('owner',)
    inlines = [DocumentShareInline]


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ('document', 'user', 'permission', 'created_at')
    search_fields = ('document__title', 'user__username', 'user__email')
    list_filter = ('permission', 'created_at')
    raw_id_fields = ('document', 'user')
