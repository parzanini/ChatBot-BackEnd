from django.urls import path
from . import views

urlpatterns = [
    path('ask/', views.ask, name='ask'),
    path('ask', views.ask, name='ask_no_slash'),
    path('upload_pdf/', views.upload_pdf, name='upload_pdf'),
    path('upload_pdf', views.upload_pdf, name='upload_pdf_no_slash'),
    path('scrape_url/', views.scrape_url, name='scrape_url'),
    path('scrape_url', views.scrape_url, name='scrape_url_no_slash')
]

