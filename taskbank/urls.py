from django.urls import path
from .views import index, task_detail, submit_solution

urlpatterns = [
    path('', index, name='index'),
    path('task/<int:task_id>/<int:language_id>/', task_detail, name='task_detail'),
    path('task/<int:task_id>/<int:language_id>/submit/', submit_solution, name='submit_solution'),
]
