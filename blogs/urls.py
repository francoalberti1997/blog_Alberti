from django.urls import path
from . import views

urlpatterns = [
    path('', views.blog_list, name='blog_list'),
    path('popular/', views.featured_blog_list, name='featured_blog_list'),
    path('<int:pk>/', views.blog_list, name='blog_list'),
]
