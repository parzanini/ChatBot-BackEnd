from django.urls import path
from . import views

urlpatterns = [
    path('ask/', views.ask, name='ask'),
    path('ask', views.ask, name='ask_no_slash')
]

