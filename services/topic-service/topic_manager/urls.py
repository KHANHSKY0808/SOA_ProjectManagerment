from django.urls import path
from .views import HealthView, TopicDetailView, TopicListCreateView
from .registration_lookup import RegistrationTopicView

urlpatterns = [path("health/", HealthView.as_view(), name="health")]
urlpatterns += [
    path("api/v1/registration-topics/", RegistrationTopicView.as_view()),
    path("api/v1/registration-topics/<str:pk>/", RegistrationTopicView.as_view()),
]
for prefix, name in [("api/", "topic"), ("api/v1/", "topic-v1")]:
    urlpatterns += [
        path(prefix + "topics/", TopicListCreateView.as_view(), name=name + "-list"),
        path(prefix + "topics/<str:pk>/", TopicDetailView.as_view(), name=name + "-detail"),
    ]
