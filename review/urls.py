from django.urls import path

from review import views

urlpatterns = [
    path("", views.index, name="review-index"),
    path("api/chart-data", views.api_chart_data, name="review-api-chart-data"),
]
