from django.shortcuts import render
from django.http import JsonResponse

# Create your views here.

def index(request):
    """Simple health-check / index for the core app."""
    return JsonResponse({"status": "ok", "app": "core"})
