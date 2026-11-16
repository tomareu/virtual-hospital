from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Route all API requests to the patients app
    path('api/', include('patients.urls')),

    # Route all analytics requests to the analytics app
    path('api/analytics/', include('analytics.urls')),

    # Route all whiteboard requests to the board app
    path('api/board/', include('board.urls')),

    # Route all report requests to the reports app
    path('api/reports/', include('reports.urls')),
]