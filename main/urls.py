from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('progress/', views.progress, name='progress'),
    path('upload/', views.upload, name='upload'),
    path('tasks/', views.tasks, name='tasks'),
    path('tasks/add/', views.add_task, name='add_task'),
    path('tasks/toggle/<int:task_id>/', views.toggle_task, name='toggle_task'),
    path('tasks/delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('tasks/edit/<int:task_id>/', views.edit_task, name='edit_task'),
    path('tasks/schedule/add/', views.add_schedule_item, name='add_schedule'),
    path('tasks/schedule/delete/<int:item_id>/', views.delete_schedule_item, name='delete_schedule'),
    path('summarize/', views.summarize_doc, name='summarize_doc'),
    path('summarize_batch/', views.summarize_batch, name='summarize_batch'),
    path('collaborate/', views.collaborate, name='collaborate'),
    path('collaborate/share/', views.share_material, name='share_material'),
    path('collaborate/like/<int:material_id>/', views.toggle_like_material, name='like_material'),
    path('collaborate/comments/<int:material_id>/', views.get_material_comments, name='get_comments'),
    path('collaborate/comments/<int:material_id>/add/', views.add_comment, name='add_comment'),
    path('profile/', views.profile, name='profile'),
]