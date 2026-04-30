from django.urls import path
from .core import OptimizeRouteView, test_api, urlpatterns

# Re-export urlpatterns for Django
app_name = 'api'