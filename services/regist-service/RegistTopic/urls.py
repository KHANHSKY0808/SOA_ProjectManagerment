from django.urls import path
from .views import AvailableTopicsView, RegistrationCancelView, RegistrationListCreateView

urlpatterns = [
    path("registrations/", RegistrationListCreateView.as_view()),
    path("registrations/<str:pk>/", RegistrationCancelView.as_view()),
    path("available-topics/", AvailableTopicsView.as_view()),
]
