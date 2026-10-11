"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from .health import health
from LectureManager.display_names import TopicDisplayNamesView
from profile_management import StudentProfileView, LecturerProfileView
from StudentManager.display_names import StudentDisplayNamesView
from registration_context import RegistrationContextView, MajorDepartmentsView

urlpatterns = [
    path("api/v1/student-display-names/", StudentDisplayNamesView.as_view()),
    path("api/v1/registration-context/", RegistrationContextView.as_view()),
    path("api/v1/major-departments/", MajorDepartmentsView.as_view()),
    path("api/v1/students/", StudentProfileView.as_view()),
    path("api/v1/students/<str:pk>/", StudentProfileView.as_view()),
    path("api/v1/lecturers/", LecturerProfileView.as_view()),
    path("api/v1/lecturers/<str:pk>/", LecturerProfileView.as_view()),
    path("api/v1/topic-display-names/", TopicDisplayNamesView.as_view(), name="topic-display-names"),
    path("health/", health, name="health"),
    path('admin/', admin.site.urls),
    path('api/', include('DeparmentManager.urls')),
    path('api/', include('MajorManager.urls')),
    path('api/', include('SubMajorManager.urls')),
    path('api/', include('StudentManager.urls')),
    path('api/', include('LectureManager.urls')),
]
