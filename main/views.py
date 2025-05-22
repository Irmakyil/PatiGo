from django.shortcuts import render, redirect, get_object_or_404
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.models import User
from .models import UserProfile, Task, FoodSource
from django.contrib import messages
import re
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import datetime
from django.core.mail import send_mail
from django.conf import settings
import random
import string
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
import json
from django.db.models import Sum
from django.db.models import Q
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderServiceError
from django.shortcuts import render, redirect
import time


# Create your views here.

def home(request):
    
    active_feeding_points = FoodSource.objects.filter(status='bekliyor').count()
    volunteers_count = UserProfile.objects.filter(user_type='gonullu').count()
    food_sources_count = FoodSource.objects.count()

   
    one_week_ago = timezone.now() - datetime.timedelta(days=7)
    weekly_food_count = FoodSource.objects.filter(reported_at__gte=one_week_ago).count()

    context = {
        'active_feeding_points': active_feeding_points,
        'volunteers_count': volunteers_count,
        'food_sources_count': food_sources_count,
        'weekly_food_count': weekly_food_count,
    }
    return render(request, 'home.html', context)




def gorev_noktalari(request):
    if request.method == 'POST':
        food_id = request.POST.get('food_id')
        food = FoodSource.objects.filter(id=food_id, status='bekliyor').first()
        if food:
            food.status = 'teslim'
            food.save()
        return redirect('gorev_noktalari')  # map.html'e yönlendiren url ismi neyse onu kullan

    foods = FoodSource.objects.all().order_by('-reported_at')
    foods_json = json.dumps([
        {
            'id': food.id,
            'lat': food.latitude,
            'lng': food.longitude,
            'location': food.location,
            'amount': food.amount,
            'description': food.description,
            'photo_url': food.photo.url if food.photo else None,
            'reported_at': food.reported_at.strftime('%d.%m.%Y, %H:%M')
        }
        for food in foods if food.latitude and food.longitude
    ])

    return render(request, 'gorev_noktalari.html', {
        'foods': foods,
        'foods_json': foods_json
    })


def gonullu_ol(request):
    from .models import Task
    all_tasks = Task.objects.all()
    return render(request, 'gonullu_ol.html', {'all_tasks': all_tasks})

def sifremi_unuttum(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            # Geçici şifre oluştur
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user.set_password(temp_password)
            user.save()
            
            try:
                # E-posta gönder
                subject = 'Şifre Sıfırlama - PatiGo'
                message = f'Sayın {user.username},\n\nGeçici şifreniz: {temp_password}\n\nGüvenliğiniz için lütfen giriş yaptıktan sonra şifrenizi değiştirin.'
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                messages.success(request, 'Geçici şifreniz e-posta adresinize gönderildi.')
                return redirect('giris')
            except Exception as e:
                # E-posta gönderimi başarısız olursa şifreyi geri al
                user.set_password(user.password)
                user.save()
                messages.error(request, 'E-posta gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.')
                return render(request, 'sifremi_unuttum.html')
        except User.DoesNotExist:
            messages.error(request, 'Bu e-posta adresi ile kayıtlı bir kullanıcı bulunamadı.')
        except Exception as e:
            messages.error(request, 'Bir hata oluştu. Lütfen daha sonra tekrar deneyin.')
    return render(request, 'sifremi_unuttum.html')
    return render(request, 'sifremi_unuttum.html')
@login_required
def sifre_degistir(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            return redirect('giris')  
    else:
        form = PasswordChangeForm(user=request.user)
  
    return render(request, 'sifre_degistir.html', {'form': form})
    messages.success(request, 'Şifreniz başarı ile değiştirildi. Tekrar giriş yapınız.')

def giris(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Kullanıcı tipine göre yönlendirme (şimdilik gönüllü paneli)
            try:
                profile = user.userprofile
                if profile.user_type == 'gonullu':
                    return redirect('gonullu_panel')
                else:
                    return redirect('home')
            except:
                return redirect('home')
        else:
            messages.error(request, 'Kullanıcı adı veya şifre hatalı.')
            return render(request, 'giris.html')
    return render(request, 'giris.html')

def kayit(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        user_type = request.POST.get('user_type')

        # Şifre kuralları
        if len(password1) < 8 or not re.search(r'[A-Z]', password1) or not re.search(r'[a-z]', password1) or not re.search(r'\d', password1):
            messages.error(request, 'Şifre kurallarına uygun değil.')
            return render(request, 'kayit.html')
        if password1 != password2:
            messages.error(request, 'Şifreler eşleşmiyor.')
            return render(request, 'kayit.html')
        if user_type not in ['gonullu', 'yetkili']:
            messages.error(request, 'Kullanıcı tipi seçmelisiniz.')
            return render(request, 'kayit.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Bu kullanıcı adı zaten alınmış.')
            return render(request, 'kayit.html')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Bu e-posta zaten kayıtlı.')
            return render(request, 'kayit.html')
        # Kullanıcı oluştur
        user = User.objects.create_user(username=username, email=email, password=password1)
        UserProfile.objects.create(user=user, user_type=user_type)
        messages.success(request, 'Kayıt başarılı! Giriş yapabilirsiniz.')
        return redirect('giris')
    return render(request, 'kayit.html')

@login_required
def gonullu_panel(request):
    profile = request.user.userprofile
    if profile.user_type != 'gonullu':
        return redirect('home')
    # Görev tamamla işlemi
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        try:
            task = Task.objects.get(id=task_id, assigned_to=request.user)
            task.is_completed = True
            task.save()
            messages.success(request, 'Görev tamamlandı olarak işaretlendi.')
        except Task.DoesNotExist:
            messages.error(request, 'Görev bulunamadı.')
        return redirect('gonullu_panel')
    # Kullanıcıya atanmış ve tamamlanmamış görevler
    tasks = Task.objects.filter(assigned_to=request.user, is_completed=False)
    return render(request, 'gonullu_panel.html', {'tasks': tasks})

@login_required
def gorev_al(request):
    profile = request.user.userprofile
    if profile.user_type != 'gonullu':
        return redirect('home')
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        try:
            task = Task.objects.get(id=task_id, assigned_to__isnull=True, is_completed=False)
            task.assigned_to = request.user
            task.save()
            messages.success(request, 'Görev başarıyla alındı!')
        except Task.DoesNotExist:
            messages.error(request, 'Görev alınamıyor veya zaten alınmış.')
        return redirect('gorev_al')
    # Atanmamış ve tamamlanmamış görevler
    tasks = Task.objects.filter(assigned_to__isnull=True, is_completed=False)
    return render(request, 'gorev_al.html', {'tasks': tasks})

def cikis(request):
    logout(request)
    return redirect('home')

@login_required
def profil(request):
    profile = request.user.userprofile
    # Örnek rozetler (ileride dinamik yapılabilir)
    badges = [
        {'icon': '🐾', 'name': 'Pati Koruyucu'},
        {'icon': '🍚', 'name': 'Mama Dağıtıcısı'},
        {'icon': '💧', 'name': 'Su Kahramanı'},
        {'icon': '🧤', 'name': 'Temizlik Ustası'},
    ]
    return render(request, 'profil.html', {'profile': profile, 'badges': badges})

@login_required
def gorev_ekle(request):
    profile = request.user.userprofile
    if profile.user_type != 'yetkili':
        return redirect('home')
    edit_task = None
    # Silme işlemi
    if request.GET.get('delete'):
        try:
            task = Task.objects.get(id=request.GET.get('delete'))
            task.delete()
            messages.success(request, 'Görev silindi.')
            return redirect('gorev_ekle')
        except Task.DoesNotExist:
            messages.error(request, 'Görev bulunamadı.')
    # Düzenleme için mevcut görev
    if request.GET.get('edit'):
        try:
            edit_task = Task.objects.get(id=request.GET.get('edit'))
        except Task.DoesNotExist:
            edit_task = None
            messages.error(request, 'Görev bulunamadı.')
    # Ekleme veya düzenleme işlemi
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        name = request.POST.get('name')
        end_time = request.POST.get('end_time')
        priority = request.POST.get('priority')
        animal_count = request.POST.get('animal_count')
        status = request.POST.get('status')
        if not (name and end_time and priority and animal_count and status):
            messages.error(request, 'Tüm alanları doldurmalısınız.')
        else:
            try:
                end_time_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
                if task_id:  # Düzenleme
                    task = Task.objects.get(id=task_id)
                    task.name = name
                    task.end_time = end_time_dt
                    task.priority = priority
                    task.animal_count = animal_count
                    task.status = status
                    task.description = status
                    task.save()
                    messages.success(request, 'Görev güncellendi!')
                else:  # Yeni görev
                    Task.objects.create(
                        name=name,
                        end_time=end_time_dt,
                        priority=priority,
                        animal_count=animal_count,
                        status=status,
                        description=status
                    )
                    messages.success(request, 'Görev başarıyla eklendi!')
                return redirect('gorev_ekle')
            except Exception as e:
                messages.error(request, 'Tarih formatı hatalı veya başka bir hata oluştu.')
    tasks = Task.objects.order_by('-end_time')[:10]
    return render(request, 'gorev_ekle.html', {'tasks': tasks, 'edit_task': edit_task})

@login_required
def yemek_kaynagi_bildir(request):
    # Sadece “yetkili” kullanıcıların erişebileceğini varsayıyoruz:
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'yetkili':
        return redirect('home')

    if request.method == 'POST':
        location    = request.POST.get('location')    # Adres metni
        amount      = request.POST.get('amount')
        description = request.POST.get('description')
        photo       = request.FILES.get('photo')

        # Zorunlu alan kontrolü
        if not (location and amount):
            return render(request, 'yemek_kaynagi_bildir.html', {
                'error': 'Konum ve miktar alanları zorunludur.'
            })

        # 1. Varsayılan lat/lng değerleri
        latitude = None
        longitude = None

        # 2. Geocoding: Nominatim ile adresi koordinata çevir
        try:
            geolocator = Nominatim(user_agent="patigo_app")
            time.sleep(1)  # Nominatim’in aşırı istek engellemesini önlemek için ufak bekleme
            geo = geolocator.geocode(f"{location}, Kocaeli, Türkiye")
            if geo:
                latitude = geo.latitude
                longitude = geo.longitude
        except (GeocoderUnavailable, GeocoderServiceError):
            # Coğrafi kodlama başarısız olursa, lat/lng None kalacak
            pass

        # 3. FoodSource kaydını oluştururken lat/lng değerlerini de atıyoruz
        FoodSource.objects.create(
            location=location,
            amount=amount,
            description=description,
            photo=photo,
            reported_by=request.user,
            latitude=latitude,
            longitude=longitude
        )

        return redirect('gorev_noktalari')  # Kayıttan sonra harita sayfasına döner

    # GET isteği ise formu göster
    return render(request, 'yemek_kaynagi_bildir.html')

def arama(request):
    from django.db.models import Q
    from .models import Task, FoodSource
    query = request.GET.get('q', '')
    task_results = []
    food_results = []
    anasayfa_bulundu = False
    # Anasayfa statik metinleri
    ANASAYFA_METINLERI = [
        "Kampüs Hayvanları İçin Dijital Destek Platformu",
        "Pati Dostu, kampüsteki sokak hayvanlarına destek olmak için oluşturulmuş dijital bir platformdur.",
        "Beslenme Noktaları Haritası",
        "Yemek Artığı Planlaması",
        "Gönüllü Takip Sistemi",
        "Beslenme Takibi",
        "Beslenme Noktaları Rozetleri",
        "Acil Durum Bildirimleri",
        # ... diğer önemli anasayfa metinleri ...
    ]
    if query:
        task_results = Task.objects.filter(
            Q(name__icontains=query) | Q(status__icontains=query)
        )
        food_results = FoodSource.objects.filter(
            Q(location__icontains=query) | Q(amount__icontains=query) | Q(description__icontains=query)
        )
        for metin in ANASAYFA_METINLERI:
            if query.lower() in metin.lower():
                anasayfa_bulundu = True
                break
    return render(request, 'arama_sonuc.html', {
        'query': query,
        'task_results': task_results,
        'food_results': food_results,
        'anasayfa_bulundu': anasayfa_bulundu,
    })
    
def food_detail(request, pk):
    food = get_object_or_404(FoodSource, pk=pk)
    return render(request, 'food_detail.html', {'food': food})