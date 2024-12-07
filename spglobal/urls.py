from django.urls import path
from . import views

urlpatterns = [
    path("", views.fetch_data, name="fetch_data"),
    path(
        "constituents/<str:index_code>/",
        views.fetch_index_constituents,
        name="fetch_index_constituents",
    ),
    path(
        "historical/<str:market>/<str:interval>/",
        views.fetch_historical_data,
        name="fetch_historical_data",
    ),
    path("search/", views.search_market_data, name="search_market_data"),
]
