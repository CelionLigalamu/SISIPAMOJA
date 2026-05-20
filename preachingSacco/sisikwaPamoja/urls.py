from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('register/', 
         views.register_view, name='register'),
    path('login/', 
         views.login_view, name='login'),
    path('logout/', 
         views.logout_view, name='logout'),
    path('forgot-password/', 
         views.forgot_password_view, 
         name='forgot_password'),
     path('dashboard/member/',    
         views.member_dashboard, 
         name='member_dashboard'),
     path('dashboard/admin/',    
         views.admin_dashboard, 
         name='admin_dashboard'),
     path('delete-account/',    
         views.delete_account, 
         name='delete_account'),

     #Password reset URLs
     path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='sisikwaPamoja/password_reset.html',
             email_template_name='sisikwaPamoja/password_reset_email.html',
             subject_template_name='sisikwaPamoja/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='sisikwaPamoja/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='sisikwaPamoja/password_reset_confirm.html',
             success_url='/password-reset-complete/'
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='sisikwaPamoja/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    path('', views.home_view, name='home'),
     
]