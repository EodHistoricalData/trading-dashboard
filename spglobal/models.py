from django.db import models
from dataclasses import dataclass


class SPGlobalIndex(models.Model):
    index_id = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    constituents = models.IntegerField()
    value = models.FloatField()
    market_cap = models.FloatField(null=True, blank=True)
    divisor = models.FloatField(null=True, blank=True)
    daily_return = models.FloatField()
    dividend = models.FloatField(null=True, blank=True)
    adjusted_market_cap = models.FloatField(null=True, blank=True)
    adjusted_divisor = models.FloatField(null=True, blank=True)
    adjusted_constituents = models.IntegerField()
    currency_code = models.CharField(max_length=10)
    currency_name = models.CharField(max_length=50)
    currency_symbol = models.CharField(max_length=10)
    last_update = models.DateField()

    def __str__(self):
        return self.name


class IndexConstituent(models.Model):
    index = models.ForeignKey(
        SPGlobalIndex, on_delete=models.CASCADE, related_name="components"
    )
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    sector = models.CharField(max_length=50)
    industry = models.CharField(max_length=100)
    weight = models.FloatField()

    def __str__(self):
        return self.name


class HistoricalMarketData(models.Model):
    index_id = models.CharField(max_length=50, unique=True)
    timestamp = models.DateTimeField()
    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    volume = models.IntegerField()
    interval = models.CharField(max_length=16)

    def __str__(self):
        return f"{self.index.code} - {self.timestamp} ({self.interval})"


@dataclass
class SearchData:
    Code: str
    Exchange: str
    Name: str
    Type: str
    Country: str
    Currency: str
    ISIN: str
    previousClose: float
    previousCloseDate: str
