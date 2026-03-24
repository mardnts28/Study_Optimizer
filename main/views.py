from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
import json
import re
import io
from datetime import date, timedelta
from .models import Task, SharedMaterial, Comment, SummarizedDocument, ScheduleItem
from .services import (
    extract_text_from_file, 
    generate_document_summary, 
    generate_batch_synthesis,
    calculate_user_metrics,
    search_summarized_documents
)

@csrf_protect
def index(request):
    return render(request, "main/index.html")

@csrf_protect
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return redirect('register')

        User.objects.create_user(username=username, email=email, password=password)
        messages.success(request, "Account created successfully. Please log in.")
        return redirect('login')

    return render(request, 'main/register.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)
            return redirect("dashboard")  
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "main/login.html")

def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
@csrf_protect
def collaborate(request):
    materials = SharedMaterial.objects.all().order_by('-created_at')
    materials_list = []
    
    total_community_likes = 0
    for m in materials:
        m_likes = m.likes.count()
        total_community_likes += m_likes
        materials_list.append({
            'id': m.id,
            'title': m.title,
            'author': m.author.username,
            'authorInitials': m.author.username[:2].upper(),
            'authorColor': '#8C1007' if m.author == request.user else '#4B5563',
            'period': m.period,
            'subject': m.subject,
            'preview': m.content,
            'likes': m_likes,
            'views': m.views,
            'comments': m.comments.count(),
            'timeAgo': 'Just now',
            'emoji': m.emoji,
            'liked': m.likes.filter(id=request.user.id).exists(),
            'tags': [m.subject]
        })
    
    active_students_count = User.objects.count()
    
    # Calculate Top Contributors
    from django.db.models import Count
    top_sharers_raw = User.objects.annotate(
        shares_count=Count('shared_materials')
    ).filter(shares_count__gt=0).order_by('-shares_count')[:4]
    
    top_contributors = []
    medals = ['🥇', '🥈', '🥉', '4️⃣']
    for i, u in enumerate(top_sharers_raw):
        top_contributors.append({
            'name': u.username,
            'count': u.shares_count,
            'medal': medals[i] if i < len(medals) else str(i+1)
        })

    # Calculate Trending Topics
    trending_topics = list(SharedMaterial.objects.values('subject').annotate(
        count=Count('subject')
    ).order_by('-count').values_list('subject', flat=True)[:5])

    return render(request, "main/collaborate.html", {
        'materials_json': json.dumps(materials_list),
        'active_students': active_students_count,
        'total_community_likes': total_community_likes,
        'top_contributors': top_contributors,
        'trending_topics': trending_topics
    })

@login_required
@require_POST
def share_material(request):
    try:
        data = json.loads(request.body)
        material = SharedMaterial.objects.create(
            author=request.user,
            title=data.get('title'),
            subject=data.get('subject'),
            period=data.get('period'),
            content=data.get('preview'),
            emoji='📄'
        )
        return JsonResponse({
            'status': 'success',
            'material': {
                'id': material.id,
                'title': material.title,
                'author': material.author.username,
                'authorInitials': material.author.username[:2].upper(),
                'authorColor': '#8C1007',
                'period': material.period,
                'subject': material.subject,
                'preview': material.content,
                'likes': 0,
                'views': 0,
                'comments': 0,
                'timeAgo': 'Just now',
                'emoji': material.emoji,
                'liked': False,
                'tags': [material.subject]
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def toggle_like_material(request, material_id):
    material = get_object_or_404(SharedMaterial, id=material_id)
    if material.likes.filter(id=request.user.id).exists():
        material.likes.remove(request.user)
        liked = False
    else:
        material.likes.add(request.user)
        liked = True
    return JsonResponse({'status': 'success', 'liked': liked, 'likes_count': material.likes.count()})

@login_required
def get_material_comments(request, material_id):
    material = get_object_or_404(SharedMaterial, id=material_id)
    comments = material.comments.all().order_by('-created_at')
    comments_list = [{
        'id': c.id,
        'author': c.author.username,
        'authorInitials': c.author.username[:2].upper(),
        'authorColor': '#8C1007' if c.author == request.user else '#4B5563',
        'text': c.text,
        'timeAgo': 'Just now'
    } for c in comments]
    return JsonResponse({'status': 'success', 'comments': comments_list})

@login_required
@require_POST
def add_comment(request, material_id):
    material = get_object_or_404(SharedMaterial, id=material_id)
    data = json.loads(request.body)
    comment = Comment.objects.create(
        material=material,
        author=request.user,
        text=data.get('text')
    )
    return JsonResponse({
        'status': 'success',
        'comment': {
            'id': comment.id,
            'author': comment.author.username,
            'authorInitials': comment.author.username[:2].upper(),
            'authorColor': '#8C1007',
            'text': comment.text,
            'timeAgo': 'Just now'
        }
    })

@login_required
@csrf_protect
def dashboard(request):
    """
    User dashboard with quick stats, active tasks, and study schedule.
    """
    metrics = calculate_user_metrics(request.user)
    
    # Get top 4 active tasks
    active_tasks = Task.objects.filter(user=request.user, completed=False).order_by('due_date')[:4]
    upcoming_tasks_list = []
    for t in active_tasks:
        days_left = (t.due_date - date.today()).days
        upcoming_tasks_list.append({
            'title': t.title,
            'date': t.due_date.strftime('%b %d'),
            'priority': t.priority,
            'period': t.period,
            'daysLeft': max(0, days_left)
        })

    # Weekly Study Hours (Mon-Sun for the bar chart)
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    daily_hours = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        tasks_on_day = Task.objects.filter(user=request.user, completed=True, created_at__date=day).count()
        summaries_on_day = SummarizedDocument.objects.filter(user=request.user, created_at__date=day).count()
        daily_hours.append((tasks_on_day * 2) + (summaries_on_day * 1))

    context = {
        **metrics,
        'upcoming_tasks_json': json.dumps(upcoming_tasks_list),
        'weekly_hours_list': json.dumps(daily_hours),
        'schedule_items_json': json.dumps([{
            'id': item.id,
            'day': item.day,
            'time': item.time,
            'activity': item.activity,
            'color': item.color
        } for item in ScheduleItem.objects.filter(user=request.user)]),
    }
    return render(request, "main/dashboard.html", context)

@login_required
@csrf_protect
def progress(request):
    """
    Comprehensive progress tracker showing streaks, hours, and subject heatmaps.
    """
    metrics = calculate_user_metrics(request.user)
    
    period_stats = [
        {'period': 'General Progress', 'completed': metrics['completed_count'], 'total': metrics['total_tasks']}
    ]
    
    context = {
        **metrics,
        'period_stats_json': json.dumps(period_stats),
        'subject_labels_json': json.dumps(metrics['subject_labels']),
        'subject_data_json': json.dumps(metrics['subject_data']),
        'weekly_hours_json': json.dumps(metrics['weekly_hours_trend']),
    }
    return render(request, "main/progress.html", context)

@login_required
@csrf_protect
def upload(request):
    # Handle max document summaries: Increased limit to 50 for the sidebar
    recent_summaries = SummarizedDocument.objects.filter(user=request.user).order_by('-created_at')[:50]
    summaries_list = []
    for s in recent_summaries:
        summaries_list.append({
            'id': s.id,
            'title': s.file_name,
            'period': 'General',
            'date': s.created_at.strftime('%b %d'),
            'emoji': s.emoji,
            'summary': s.summary_text
        })
    return render(request, "main/upload.html", {
        'recent_summaries_json': json.dumps(summaries_list)
    })


@login_required
@require_POST
def summarize_doc(request):
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No file uploaded'}, status=400)
        
        uploaded_file = request.FILES['file']
        file_name = uploaded_file.name
        
        # Text Extraction per File Type
        content = extract_text_from_file(uploaded_file)
        
        if not content:
            return JsonResponse({'status': 'error', 'message': 'Could not extract text from document'}, status=400)

        # AI Summarization Logic (Extractive)
        final_summary, title_line = generate_document_summary(content, file_name)

        # Save to DB
        doc = SummarizedDocument.objects.create(
            user=request.user,
            file_name=file_name,
            period='General',
            summary_text=final_summary,
            emoji='📄'
        )

        return JsonResponse({
            'status': 'success',
            'summary': final_summary,
            'title': title_line,
            'doc_id': doc.id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def summarize_batch(request):
    try:
        data = json.loads(request.body)
        doc_ids = data.get('doc_ids', [])
        
        if not doc_ids:
            return JsonResponse({'status': 'error', 'message': 'No documents provided for batch processing'}, status=400)
            
        batch_output = generate_batch_synthesis(doc_ids, request.user)
        
        if not batch_output:
             return JsonResponse({'status': 'error', 'message': 'Documents not found or synthesis failed'}, status=404)
        
        return JsonResponse({
            'status': 'success',
            'combined_summary': batch_output
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@csrf_protect
def tasks(request):
    user_tasks = Task.objects.filter(user=request.user).order_by('completed', 'due_date')
    tasks_json = []
    for t in user_tasks:
        tasks_json.append({
            'id': t.id,
            'title': t.title,
            'period': t.period,
            'priority': t.priority,
            'dueDate': t.due_date.strftime('%Y-%m-%d'),
            'completed': t.completed
        })
    
    return render(request, "main/tasks.html", {'tasks_data': json.dumps(tasks_json)})

@login_required
@require_POST
def add_task(request):
    try:
        data = json.loads(request.body)
        task = Task.objects.create(
            user=request.user,
            title=data.get('title'),
            period=data.get('period'),
            priority=data.get('priority'),
            due_date=data.get('dueDate')
        )
        return JsonResponse({
            'status': 'success',
            'task': {
                'id': task.id,
                'title': task.title,
                'period': task.period,
                'priority': task.priority,
                'dueDate': task.due_date.strftime('%Y-%m-%d'),
                'completed': task.completed
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def edit_task(request, task_id):
    try:
        task = get_object_or_404(Task, id=task_id, user=request.user)
        data = json.loads(request.body)
        task.title = data.get('title', task.title)
        task.period = 'General'
        task.priority = data.get('priority', task.priority)
        task.due_date = data.get('dueDate', task.due_date)
        task.save()
        return JsonResponse({
            'status': 'success',
            'task': {
                'id': task.id,
                'title': task.title,
                'period': task.period,
                'priority': task.priority,
                'dueDate': task.due_date.strftime('%Y-%m-%d'),
                'completed': task.completed
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def toggle_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    task.completed = not task.completed
    task.save()
    return JsonResponse({'status': 'success', 'completed': task.completed})

@login_required
@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    task.delete()
    return JsonResponse({'status': 'success'})

@login_required
@csrf_protect
def profile(request):
    """
    User profile viewing level and academic success metrics.
    Supports POST for editing profile data.
    """
    # Ensure profile exists
    from .models import Profile
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            bio = data.get('bio', '').strip()
            major = data.get('major', '').strip()
            
            if not username:
                return JsonResponse({'status': 'error', 'message': 'Username cannot be empty'}, status=400)
            
            # Check username uniqueness if changed
            if username != request.user.username and User.objects.filter(username=username).exists():
                return JsonResponse({'status': 'error', 'message': 'Username already taken'}, status=400)
            
            request.user.username = username
            request.user.email = email
            request.user.save()
            
            profile.bio = bio
            profile.major = major
            profile.save()
            
            return JsonResponse({'status': 'success', 'message': 'Profile updated successfully!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    metrics = calculate_user_metrics(request.user)
    metrics['profile'] = profile
    return render(request, "main/profile.html", metrics)

@login_required
@require_POST
def add_schedule_item(request):
    try:
        data = json.loads(request.body)
        item = ScheduleItem.objects.create(
            user=request.user,
            day=data.get('day'),
            time=data.get('time'),
            activity=data.get('activity'),
            color=data.get('color', 'blue')
        )
        return JsonResponse({
            'status': 'success',
            'item': {
                'id': item.id,
                'day': item.day,
                'time': item.time,
                'activity': item.activity,
                'color': item.color
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def delete_schedule_item(request, item_id):
    item = get_object_or_404(ScheduleItem, id=item_id, user=request.user)
    item.delete()
    return JsonResponse({'status': 'success'})

@login_required
def search_documents(request):
    """
    Global search across summarized documents using PostgreSQL full-text search.
    """
    query = request.GET.get('q', '')
    results = search_summarized_documents(request.user, query)
    
    formatted_results = [{
        'id': r.id,
        'title': r.file_name,
        'summary': r.summary_text[:200] + '...',
        'emoji': r.emoji,
        'date': r.created_at.strftime('%Y-%m-%d')
    } for r in results]
    
    return JsonResponse({'status': 'success', 'results': formatted_results})
