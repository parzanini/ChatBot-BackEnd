from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('register', views.register, name='register_no_slash'),
    path('login/', views.login, name='login'),
    path('login', views.login, name='login_no_slash'),
    path('logout/', views.logout, name='logout'),
    path('logout', views.logout, name='logout_no_slash'),
    path('ask/', views.ask, name='ask'),
    path('ask', views.ask, name='ask_no_slash'),
    path('upload_pdf/', views.upload_pdf, name='upload_pdf'),
    path('upload_pdf', views.upload_pdf, name='upload_pdf_no_slash'),
    path('index_database/', views.index_database, name='index_database'),
    path('index_database', views.index_database, name='index_database_no_slash'),
    path('index_database_runs/', views.index_database_runs, name='index_database_runs'),
    path('index_database_runs', views.index_database_runs, name='index_database_runs_no_slash'),
    path('manual_uploads/', views.manual_uploads, name='manual_uploads'),
    path('manual_uploads', views.manual_uploads, name='manual_uploads_no_slash'),
    path('keep_alive/', views.keep_alive, name='keep_alive'),
    path('keep_alive', views.keep_alive, name='keep_alive_no_slash')
]
