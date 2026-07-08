from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("history/", views.history, name="history"),
    path("queue/", views.my_queue, name="my_queue"),
    path("api/employees/search/", views.employee_search, name="employee_search"),
    path("incidents/new/", views.incident_create, name="incident_create"),
    path("incidents/<int:pk>/", views.incident_detail, name="incident_detail"),
    path("incidents/<int:pk>/edit/", views.incident_edit, name="incident_edit"),
    path("incidents/<int:pk>/verify/", views.incident_verify, name="incident_verify"),
    path("incidents/<int:pk>/reject-verify/", views.incident_reject_verify, name="incident_reject_verify"),
    path("incidents/<int:pk>/approve/", views.incident_approve, name="incident_approve"),
    path("incidents/<int:pk>/reject-approve/", views.incident_reject_approve, name="incident_reject_approve"),
    path("incidents/<int:pk>/forward/", views.incident_forward, name="incident_forward"),
    path("incidents/<int:pk>/comment/", views.incident_comment, name="incident_comment"),
    path("incidents/<int:pk>/pdf/", views.incident_pdf, name="incident_pdf"),
    path("incidents/<int:pk>/photos/<int:photo_pk>/delete/", views.photo_delete, name="photo_delete"),
]
