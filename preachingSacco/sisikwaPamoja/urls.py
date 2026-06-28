from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home
    path('', views.home_view, name='home'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/',
         views.forgot_password_view,
         name='forgot_password'),

    # Dashboards
    path('dashboard/member/',
         views.member_dashboard,
         name='member_dashboard'),
    path('dashboard/admin/',
         views.admin_dashboard,
         name='admin_dashboard'),

    # Profile
    path('profile/',
         views.profile_view,
         name='profile'),
    path('profile_edit/',
         views.profile_edit_view,
         name='profile_edit'),

    # Contributions
    path('contributions/',
         views.contributions_view,
         name='contributions'),

    # Savings
    path('savings/',
         views.savings_view,
         name='savings'),

    # Loans
    path('loans/',
         views.loans_view,
         name='loans'),
    path('loans/apply/',
         views.loan_apply_view,
         name='loan_apply'),

    # Family Coverage
    path('family/',
         views.family_view,
         name='family'),
    path('family/add-dependant/',
         views.add_dependant_view,
         name='add_dependant'),

    # Statements
    path('statements/',
         views.statements_view,
         name='statements'),

    # Notifications
    path('notifications/',
         views.notifications_view,
         name='notifications'),

    # Settings
    path('settings/',
         views.settings_view,
         name='settings'),

    # Delete Account
    path('delete-account/',
         views.delete_account,
         name='delete_account'),

    # Password Reset
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

     #Mpesa Payment
     path('pay/',
     views.mpesa_payment_view,
     name='mpesa_payment'),

     path('mpesa/callback/',
          views.mpesa_callback,
          name='mpesa_callback'),
]