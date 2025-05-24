from .models import UserProfile, Task, FoodSource,Badge, UserBadge
from django.contrib import admin

# Register your models here.
admin.site.register(UserProfile)
admin.site.register(Task)
admin.site.register(FoodSource)

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'awarded_at')