from django.urls import path
from .management_roster import TopicRegistrationsView, TopicRegistrationDetailView
from .views import AvailableTopicsView, RegistrationCancelView, RegistrationListCreateView

urlpatterns = [
    path("topics/<str:topic_id>/registrations/<str:registration_id>/", TopicRegistrationDetailView.as_view()),
    path("topics/<str:topic_id>/registrations/", TopicRegistrationsView.as_view()),
    path("registrations/", RegistrationListCreateView.as_view()),
    path("registrations/<str:pk>/", RegistrationCancelView.as_view()),
    path("available-topics/", AvailableTopicsView.as_view()),
]
