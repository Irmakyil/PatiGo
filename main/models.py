from django.db import models
from django.contrib.auth.models import User
from geopy.exc import GeocoderUnavailable, GeocoderServiceError
import time
from geopy.geocoders import Nominatim
from django.utils.crypto import get_random_string
from django.utils import timezone
import datetime

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
    location = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=100)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    is_completed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tasks')

    def _str_(self):
        return self.name

class FoodSource(models.Model):
    STATUS_CHOICES = (
        ('bekliyor', 'Bekliyor'),
        ('teslim', 'Teslim Alındı'),
    )
    location = models.CharField(max_length=200)
    amount = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='food_photos/', blank=True, null=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='bekliyor')
    reported_at = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.location} - {self.amount}"
    
    def save(self, *args, **kwargs):
        # Eğer latitude veya longitude boşsa, geocode yap
        if (self.latitude is None or self.longitude is None) and self.location:
            try:
                geolocator = Nominatim(user_agent="patigo_app")
                # API hızı sınırlaması olabilir; istekler arası ufak bir bekleme koyuyoruz
                time.sleep(1)
                geo = geolocator.geocode(self.location + ", Kocaeli Türkiye")
                if geo:
                    self.latitude = geo.latitude
                    self.longitude = geo.longitude
            except (GeocoderUnavailable, GeocoderServiceError):
                # Geocoding sırasında hata olursa sadece kaydet, lat/lng boş kalacak
                pass

        super().save(*args, **kwargs)


class Badge(models.Model): #rozetleri tutar
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=255, blank=True, null=True)  # Artık sadece yol tutacak
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class UserBadge(models.Model): #hangi rozetin kazanıldığı
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"
    
class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {'Verified' if self.is_verified else 'Not Verified'}"

    @classmethod
    def create_verification(cls, user):
        token = get_random_string(length=32)
        verification = cls.objects.create(user=user, token=token)
        return verification

    def is_token_expired(self):
        expiration_time = self.created_at + datetime.timedelta(hours=24)
        return timezone.now() > expiration_time