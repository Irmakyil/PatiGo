from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class UserProfile(models.Model):
    USER_TYPES = (
        ('gonullu', 'Gönüllü'),
        ('yetkili', 'Yetkili'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    join_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_user_type_display()})"

class Task(models.Model):
    PRIORITY_CHOICES = (
        ('acil', 'Acil'),
        ('orta', 'Orta Öncelik'),
        ('normal', 'Normal'),
    )
    name = models.CharField(max_length=100)
    description = models.TextField()
    animal_count = models.PositiveIntegerField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=100)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class FoodSource(models.Model):
    STATUS_CHOICES = (
        ('bekliyor', 'Bekliyor'),
        ('teslim', 'Teslim Alındı'),
    )
    location = models.CharField(max_length=200)
    amount = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='food_photos/', blank=True, null=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='bekliyor')
    reported_at = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.location} - {self.amount}"
