from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('gorev-noktalari', views.gorev_noktalari, name='gorev_noktalari'),
    path('gonullu-ol', views.gonullu_ol, name='gonullu_ol'),
    path('giris', views.giris, name='giris'),
    path('kayit', views.kayit, name='kayit'),
    path('gonullu-panel', views.gonullu_panel, name='gonullu_panel'),
    path('gorev-al', views.gorev_al, name='gorev_al'),
    path('profil', views.profil, name='profil'),
    path('cikis', views.cikis, name='cikis'),
    path('gorev-ekle', views.gorev_ekle, name='gorev_ekle'),
    path('yemek-kaynagi-bildir', views.yemek_kaynagi_bildir, name='yemek_kaynagi_bildir'),
    path('arama', views.arama, name='arama'),
    path('sifremi_unuttum', views.sifremi_unuttum, name='sifremi_unuttum'),
    path('sifre_degistir', views.sifre_degistir, name='sifre_degistir'),
    path('food/<int:pk>/', views.food_detail, name='food_detail'),
] 