# your_app/models.py
from django.db import models

class FuelStation(models.Model):
    opis_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.FloatField()

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price:.3f})"

    class Meta:
        ordering = ['city', 'state']