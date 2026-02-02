from django.urls import path
from . import views

urlpatterns = [
    path('ask/', views.ask, name='ask'),
    path('ask', views.ask, name='ask_no_slash'),
    path('upload_pdf/', views.upload_pdf, name='upload_pdf'),
    path('upload_pdf', views.upload_pdf, name='upload_pdf_no_slash'),
    path('index_database/', views.index_database, name='index_database'),
    path('index_database', views.index_database, name='index_database_no_slash')
]

