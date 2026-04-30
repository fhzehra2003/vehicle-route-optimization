from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import FuelStation

@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'state', 'retail_price', 'latitude', 'longitude']
    list_filter = ['state', 'city']
    search_fields = ['name', 'city', 'address']
    readonly_fields = ['latitude', 'longitude']
    
    # Optional: Show only stations that have coordinates
    # list_display_links = ['name']