from .models import UserProfile, Task, FoodSource
from django.contrib import admin

# Register your models here.
admin.site.register(UserProfile)
admin.site.register(Task)
admin.site.register(FoodSource)
