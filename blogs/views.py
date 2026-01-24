from django.shortcuts import render
from django.http import JsonResponse
from .models import Blog

from django.http import JsonResponse
from .models import Blog

def blog_list(request, pk=None):
    def serialize_blog(blog):
        return {
            'id': blog.id,
            'title': blog.title,
            'description': blog.description,
            'body': blog.body,
            'author_image': getattr(blog.author, 'image', None),
            'category': blog.category,
            'date': blog.date,
            'read_time': blog.read_time,
            'image': blog.image,
            'is_featured': blog.is_featured,
            'author': getattr(blog.author, 'name', None),
            'youtube_id': blog.youtube_id,  
        }

    if pk:
        try:
            blog = Blog.objects.get(pk=pk)
            return JsonResponse(serialize_blog(blog))
        except Blog.DoesNotExist:
            return JsonResponse({'error': 'Blog not found'}, status=404)
    else:
        blogs = Blog.objects.all()
        data = [serialize_blog(blog) for blog in blogs]
        return JsonResponse(data, safe=False)


def featured_blog_list(request):
    blogs = Blog.objects.filter(is_featured=True).values()
    return JsonResponse(list(blogs), safe=False)
