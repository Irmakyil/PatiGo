from django.shortcuts import render
from django.contrib.auth.models import User
from .models import UserProfile, Task
from django.shortcuts import redirect
from django.contrib import messages
import re
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime
from .models import FoodSource
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
import random
import string

# Create your views here.

def home(request):
    return render(request, 'home.html')

def gorev_noktalari(request):
    from .models import FoodSource
    foods = []
    if request.user.is_authenticated:
        foods = FoodSource.objects.filter(status='bekliyor').order_by('-reported_at')[:10]
    if request.method == 'POST' and request.user.is_authenticated:
        # Gönüllü teslim alma işlemi
        if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'gonullu':
            food_id = request.POST.get('food_id')
            try:
                food = FoodSource.objects.get(id=food_id)
                food.status = 'teslim'
                food.save()
            except FoodSource.DoesNotExist:
                pass
        return redirect('gorev_noktalari')
    return render(request, 'gorev_noktalari.html', {'foods': foods})

def gonullu_ol(request):
    from .models import Task
    all_tasks = Task.objects.all()
    return render(request, 'gonullu_ol.html', {'all_tasks': all_tasks})

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
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'yetkili':
        return redirect('home')
    if request.method == 'POST':
        location = request.POST.get('location')
        amount = request.POST.get('amount')
        description = request.POST.get('description')
        photo = request.FILES.get('photo')
        if not (location and amount):
            messages.error(request, 'Konum ve miktar zorunlu.')
        else:
            FoodSource.objects.create(
                location=location,
                amount=amount,
                description=description,
                photo=photo,
                reported_by=request.user
            )
            messages.success(request, 'Yemek kaynağı bildirildi!')
            return redirect('yemek_kaynagi_bildir')
    foods = FoodSource.objects.order_by('-reported_at')[:10]
    return render(request, 'yemek_kaynagi_bildir.html', {'foods': foods})

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