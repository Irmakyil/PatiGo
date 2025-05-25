import csv
import json
import random
import re
import string
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable, GeocoderServiceError

from .models import Badge, EmailVerification, FoodSource, Task, UserBadge, UserProfile


def home(request):
    """Anasayfa istatistiklerini gösterir."""
    active_feeding_points = FoodSource.objects.filter(status='bekliyor').count()
    volunteers_count = UserProfile.objects.filter(user_type='gonullu').count()
    food_sources_count = FoodSource.objects.count()
    one_week_ago = datetime.now() - timedelta(days=7)
    weekly_food_count = FoodSource.objects.filter(reported_at__gte=one_week_ago).count()
    context = {
        'active_feeding_points': active_feeding_points,
        'volunteers_count': volunteers_count,
        'food_sources_count': food_sources_count,
        'weekly_food_count': weekly_food_count,
    }
    return render(request, 'home.html', context)


def gorev_noktalari(request):
    """Görev noktalarını ve haritayı gösterir."""
    if request.method == 'POST':
        food_id = request.POST.get('food_id')
        food = FoodSource.objects.filter(id=food_id, status='bekliyor').first()
        if food:
            food.status = 'teslim'
            food.save()
        return redirect('gorev_noktalari')

    all_foods = FoodSource.objects.all()
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
        for food in all_foods if food.latitude and food.longitude
    ])
    foods = FoodSource.objects.filter(reported_by__userprofile__user_type='yetkili').order_by('-reported_at')
    
    return render(request, 'gorev_noktalari.html', {
        'foods': foods,
        'foods_json': foods_json
    })


def gonullu_ol(request):
    """Gönüllü olma sayfası ve takvim."""
    all_tasks = Task.objects.all()
    return render(request, 'gonullu_ol.html', {'all_tasks': all_tasks})


def sifremi_unuttum(request):
    """Şifremi unuttum işlemleri."""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user.set_password(temp_password)
            user.save()
            try:
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
            except Exception:
                user.set_password(user.password)
                user.save()
                messages.error(request, 'E-posta gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.')
                return render(request, 'sifremi_unuttum.html')
        except User.DoesNotExist:
            messages.error(request, 'Bu e-posta adresi ile kayıtlı bir kullanıcı bulunamadı.')
        except Exception:
            messages.error(request, 'Bir hata oluştu. Lütfen daha sonra tekrar deneyin.')
    return render(request, 'sifremi_unuttum.html')


@login_required
def sifre_degistir(request):
    """Şifre değiştirme işlemleri."""
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            return redirect('giris')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'sifre_degistir.html', {'form': form})


def giris(request):
    """Kullanıcı girişi işlemleri."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            try:
                profile = user.userprofile
                if profile.user_type == 'gonullu':
                    return redirect('gonullu_panel')
                else:
                    return redirect('home')
            except Exception:
                return redirect('home')
        else:
            messages.error(request, 'Kullanıcı adı veya şifre hatalı.')
            return render(request, 'giris.html')
    return render(request, 'giris.html')


def kayit(request):
    """Kullanıcı kayıt işlemleri."""
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
        user = User.objects.create_user(username=username, email=email, password=password1)
        UserProfile.objects.create(user=user, user_type=user_type)
        try:
            send_verification_email(user)
            messages.success(request, 'Kayıt başarılı! Lütfen e-posta adresinizi doğrulayın.')
        except Exception:
            messages.error(request, 'E-posta gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.')
            user.delete()
            return render(request, 'kayit.html')
        return redirect('giris')
    return render(request, 'kayit.html')


@login_required
def gonullu_panel(request):
    """Gönüllü paneli: Atanmış, tamamlanmamış görevler listelenir. Görev tamamlandığında rozet ataması yapılır."""
    profile = request.user.userprofile
    if profile.user_type != 'gonullu':
        return redirect('home')

    user_badges = UserBadge.objects.filter(user=request.user).select_related('badge')

    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        task = get_object_or_404(Task, id=task_id, assigned_to=request.user, is_completed=False)
        task.is_completed = True
        task.save()
        assign_badge_if_eligible(request.user, task)
        messages.success(request, 'Görev tamamlandı ve rozetiniz güncellendi!')
        return redirect('gonullu_panel')

    tasks = Task.objects.filter(assigned_to=request.user, is_completed=False).order_by('end_time')
    context = {
        'tasks': tasks,
        'user_badges': user_badges,
    }
    return render(request, 'gonullu_panel.html', context)


@login_required
def gorev_al(request):
    """Gönüllünün yeni görev alabileceği sayfa. Atanmamış ve tamamlanmamış görevleri listeler. Seçilen görevi kullanıcıya atar."""
    profile = request.user.userprofile
    if profile.user_type != 'gonullu':
        return redirect('home')

    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        task = get_object_or_404(Task, id=task_id, assigned_to__isnull=True, is_completed=False)
        task.assigned_to = request.user
        task.save()
        messages.success(request, 'Görev başarıyla alındı!')
        return redirect('gorev_al')

    tasks = Task.objects.filter(assigned_to__isnull=True, is_completed=False).order_by('end_time')
    return render(request, 'gorev_al.html', {'tasks': tasks})


def cikis(request):
    """Kullanıcı çıkış işlemi."""
    logout(request)
    return redirect('home')


@login_required
def profil(request):
    """Kullanıcı profil sayfası ve rozetler."""
    user_badges = UserBadge.objects.filter(user=request.user).select_related('badge')
    profile = request.user.userprofile
    return render(request, 'profil.html', {'user_badges': user_badges, 'profile': profile})


@login_required
def gorev_ekle(request):
    """Yetkili kullanıcılar için görev ekleme, düzenleme ve silme işlemleri."""
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
            return redirect('gorev_ekle')

    # Düzenleme için veriyi getirme
    if request.GET.get('edit'):
        try:
            edit_task = Task.objects.get(id=request.GET.get('edit'))
        except Task.DoesNotExist:
            edit_task = None
            messages.error(request, 'Görev bulunamadı.')

    # Ekleme veya Güncelleme
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        name = request.POST.get('name')
        end_time = request.POST.get('end_time')
        priority = request.POST.get('priority')
        animal_count = request.POST.get('animal_count')
        status = request.POST.get('status')
        location = request.POST.get('location')

        if not (name and end_time and priority and animal_count and status and location):
            messages.error(request, 'Tüm alanları doldurmalısınız.')
        else:
            try:
                end_time_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
                if task_id:
                    task = Task.objects.get(id=task_id)
                    task.name = name
                    task.end_time = end_time_dt
                    task.priority = priority
                    task.animal_count = animal_count
                    task.status = status
                    task.location = location
                    task.save()
                    messages.success(request, 'Görev güncellendi!')
                else:
                    Task.objects.create(
                        name=name,
                        end_time=end_time_dt,
                        priority=priority,
                        animal_count=animal_count,
                        status=status,
                        location=location
                    )
                    messages.success(request, 'Görev başarıyla eklendi!')
                return redirect('gorev_ekle')
            except ValueError:
                messages.error(request, 'Tarih formatı hatalı. Lütfen geçerli bir tarih seçin.')
            except Exception as e:
                messages.error(request, 'Beklenmeyen bir hata oluştu: ' + str(e))

    tasks = Task.objects.order_by('-end_time')[:10]
    
    # Yeşil ikonlar için dinamik konumlar
    yesil_nokta_lokasyonlar = list(
        FoodSource.objects.filter(description__icontains="Görev Noktası")
        .values_list('location', flat=True)
        .distinct()
    )
    return render(request, 'gorev_ekle.html', {'tasks': tasks, 'edit_task': edit_task, 'yesil_nokta_lokasyonlar': yesil_nokta_lokasyonlar})

@login_required
def yemek_kaynagi_bildir(request):
    """Yetkili kullanıcılar için yemek kaynağı bildirme işlemleri."""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'yetkili':
        return redirect('home')

    if request.method == 'POST':
        location = request.POST.get('location')
        amount = request.POST.get('amount')
        description = request.POST.get('description')
        photo = request.FILES.get('photo')

        if not location:
            return render(request, 'yemek_kaynagi_bildir.html', {
                'error': 'Konum alanı zorunludur.'
            })

        latitude = None
        longitude = None

        try:
            geolocator = Nominatim(user_agent="patigo_app")
            time.sleep(1)
            geo = geolocator.geocode(f"{location}, Kocaeli, Türkiye")
            if geo:
                latitude = geo.latitude
                longitude = geo.longitude
        except (GeocoderUnavailable, GeocoderServiceError):
            pass

        FoodSource.objects.create(
            location=location,
            amount=amount,
            description=description,
            photo=photo,
            reported_by=request.user,
            latitude=latitude,
            longitude=longitude
        )
        return redirect('gorev_noktalari')

    kirmizi_nokta_lokasyonlar = list(
        FoodSource.objects.filter(description__icontains="Yemek Artık Noktası")
        .values_list('location', flat=True)
        .distinct()
    )
    return render(request, 'yemek_kaynagi_bildir.html', {
        'kirmizi_nokta_lokasyonlar': kirmizi_nokta_lokasyonlar,
    })


def arama(request):
    """Genel arama fonksiyonu: Görevler ve yemek kaynakları için."""
    query = request.GET.get('q', '')
    task_results = Task.objects.all()
    food_results = FoodSource.objects.all()
    if query:
        task_results = task_results.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(status__icontains=query)
        )
        food_results = food_results.filter(
            Q(location__icontains=query) |
            Q(amount__icontains=query) |
            Q(description__icontains=query)
        )
    task_results = task_results.order_by('-end_time')
    food_results = food_results.order_by('-reported_at')
    return render(request, 'arama_sonuc.html', {
        'query': query,
        'task_results': task_results,
        'food_results': food_results,
    })


def food_detail(request, pk):
    """Yemek kaynağı detay sayfası."""
    food = get_object_or_404(FoodSource, pk=pk)
    return render(request, 'food_detail.html', {'food': food})


def assign_badge_if_eligible(user, task):
    """Görev adında kullanılan anahtar kelimelere göre rozet atar."""
    if not user or not task or not task.name:
        return
    name_lower = task.name.strip().lower()
    badge_map = {
        'su': {
            'name': 'Su Kahramanı',
            'icon': 'images/su_kahramani.png',
        },
        'beslenme': {
            'name': 'Mama Dağıtıcısı',
            'icon': 'images/mama_dagiticisi.png',
        },
        'temizlik': {
            'name': 'Temizlik Ustası',
            'icon': 'images/temizlik_ustasi.png',
        },
        'koruyucu': {
            'name': 'Pati Koruyucu',
            'icon': 'images/pati_koruyucu.png',
        },
    }
    badge_name = None
    for keyword, bname in badge_map.items():
        if keyword in name_lower:
            badge_name = bname
            break
    if not badge_name:
        return
    badge_obj, created = Badge.objects.get_or_create(
        name=badge_name['name'],
        defaults={
            'description': f"{badge_name['name']} rozeti",
            'icon': badge_name['icon']
        }
    )
    if not UserBadge.objects.filter(user=user, badge=badge_obj).exists():
        UserBadge.objects.create(user=user, badge=badge_obj)


@login_required
def export_tasks_csv(request):
    """Kullanıcının görevlerini CSV olarak dışa aktarır."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="gorevler_{request.user.username}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Görev Başlığı', 'Durum', 'Hayvan Sayısı', 'Bitiş Süresi', 'Tamamlandı mı?'])
    user_profile = request.user.userprofile
    if user_profile.user_type == 'yetkili':
        tasks = Task.objects.filter(
            models.Q(created_by=request.user) |
            models.Q(created_by__isnull=True) |
            models.Q(assigned_to=request.user)
        ).order_by('-end_time').distinct()
    else:
        tasks = Task.objects.filter(assigned_to=request.user).order_by('-end_time')
    for task in tasks:
        writer.writerow([
            task.name,
            task.status,
            task.animal_count,
            task.end_time.strftime('%d.%m.%Y %H:%M'),
            'Evet' if task.is_completed else 'Hayır'
        ])
    return response


def send_verification_email(user):
    """Kullanıcıya e-posta doğrulama bağlantısı gönderir."""
    verification = EmailVerification.create_verification(user)
    subject = 'E-posta Adresinizi Doğrulayın'
    html_message = render_to_string('email_dogrulama.html', {
        'user': user,
        'verification_url': f"http://127.0.0.1:8000/verify-email/{verification.token}/"
    })
    plain_message = strip_tags(html_message)
    send_mail(
        subject,
        plain_message,
        settings.EMAIL_HOST_USER,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )


def verify_email(request, token):
    """E-posta doğrulama işlemi."""
    try:
        verification = EmailVerification.objects.get(token=token)
        if verification.is_token_expired():
            messages.error(request, 'Doğrulama bağlantısının süresi dolmuş.')
            return redirect('giris')
        verification.is_verified = True
        verification.save()
        messages.success(request, 'E-posta adresiniz başarıyla doğrulandı.')
        return redirect('giris')
    except EmailVerification.DoesNotExist:
        messages.error(request, 'Geçersiz doğrulama bağlantısı.')
        return redirect('giris')

