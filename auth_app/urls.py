from django.urls import path
from auth_app import views

urlpatterns = [
    path('', views.login_view, name='authapp-login'),  
    path('logout/', views.logout_view, name='authapp-logout'),  
    path('register/', views.register, name='authapp-register'),
]
