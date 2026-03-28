from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
import json
import re
import io
from datetime import date, timedelta
from datetime import datetime
from .models import Task, SharedMaterial, Comment, SummarizedDocument, ScheduleItem
from .services import (
    extract_text_from_file, 
    generate_document_summary, 
    generate_batch_synthesis,
    calculate_user_metrics,
    search_summarized_documents
)


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)

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
        if is_admin(request.user):
            return redirect('admin_dashboard')
        return redirect("dashboard")

    if request.method == "POST":
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()


        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            login(request, user)

            if is_admin(user):
                return redirect('admin_dashboard')   # -> /admin-panel/
            else:
                return redirect("dashboard")          # -> regular user
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "main/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_dashboard(request):
    context = {
        'total_users':     User.objects.count(),
        'active_sessions': User.objects.filter(is_active=True).count(),
        'total_materials': SharedMaterial.objects.count(),
        'ai_summaries':    SummarizedDocument.objects.count(),
    }
    return render(request, 'main/admin/dashboard.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_users(request):
    from .models import Profile
    users = User.objects.filter(is_superuser=False).order_by('-date_joined').select_related('profile')
    total_tasks_completed = Task.objects.filter(completed=True).count()
 
    # Average streak across all profiles
    try:
        from django.db.models import Avg
        avg_streak = Profile.objects.aggregate(a=Avg('streak'))['a'] or 0
        avg_streak = round(avg_streak)
    except Exception:
        avg_streak = 0
 
    context = {
        'users':                users,
        'active_users':         users.filter(is_active=True).count(),
        'total_tasks_completed': total_tasks_completed,
        'avg_streak':           avg_streak,
    }
    return render(request, 'main/admin/user_management.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_collaboration(request):
    from django.db.models import Sum
    materials = SharedMaterial.objects.all().order_by('-created_at').select_related('author')
 
    total_interactions = sum(m.likes.count() + m.comments.count() for m in materials)
    total_views        = materials.aggregate(v=Sum('views'))['v'] or 0
    trending_topics    = list(
        SharedMaterial.objects.values_list('subject', flat=True)
        .annotate(c=Count('subject')).order_by('-c')[:10]
    )
 
    context = {
        'materials':          materials,
        'active_posts':       materials.count(),
        'total_interactions': total_interactions,
        'total_views':        total_views,
        'trending_topics':    trending_topics,
    }
    return render(request, 'main/admin/collaboration_control.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_ai(request):
    docs        = SummarizedDocument.objects.all().order_by('-created_at').select_related('user')
    total       = docs.count()
    # We mark docs older than 5 seconds as success for demo; adapt to your model fields
    success_ct  = total  # replace with real status field if you have one
    error_ct    = 0
    success_rate = round(success_ct / total * 100, 1) if total else 0
    error_rate   = round(error_ct   / total * 100, 1) if total else 0
 
    context = {
        'recent_docs':    docs[:10],
        'quality_docs':   docs[:4],
        'total_summaries': total,
        'success_rate':   success_rate,
        'error_rate':     error_rate,
        'avg_processing': '2.8',   # replace with real timing field if available
    }
    return render(request, 'main/admin/ai_controls.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_analytics(request):
    from django.db.models import Count
    from datetime import date, timedelta
 
    # Subject breakdown
    subject_qs = (
        Task.objects.values('subject')
        .annotate(c=Count('id'))
        .order_by('-c')[:5]
    )
    subject_labels = [s['subject'] for s in subject_qs]
    subject_counts = [s['c']       for s in subject_qs]
 
    # Tasks this week
    today          = date.today()
    week_start     = today - timedelta(days=today.weekday())
    tasks_this_week = Task.objects.filter(created_at__date__gte=week_start).count()
 
    # Weekly completed vs assigned per day
    weekly_completed, weekly_assigned = [], []
    for i in range(7):
        day = week_start + timedelta(days=i)
        weekly_completed.append(Task.objects.filter(completed=True,  created_at__date=day).count())
        weekly_assigned .append(Task.objects.filter(                  created_at__date=day).count())
 
    import json
    context = {
        'total_tasks_week':       tasks_this_week,
        'peak_productivity':      '6 PM – 9 PM',
        'most_productive_day':    'Friday',
        'subject_labels_json':    json.dumps(subject_labels),
        'subject_counts_json':    json.dumps(subject_counts),
        'weekly_completed_json':  json.dumps(weekly_completed),
        'weekly_assigned_json':   json.dumps(weekly_assigned),
    }
    return render(request, 'main/admin/analytics.html', context)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def admin_audit(request):
    context = {
        'security_events': 5, 
        'warnings_today':  3,
        'avg_rating':      '4.4',
    }
    return render(request, 'main/admin/audit_logs.html', context)

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
        content = extract_text_from_file(uploaded_file)
        
        if not content:
            return JsonResponse({'status': 'error', 'message': 'Could not extract text from document'}, status=400)

        final_summary, title_line = generate_document_summary(content, file_name)

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
def tasks_view(request):
    tasks = Task.objects.filter(user=request.user)
    tasks_data = []
    for t in tasks:
        tasks_data.append({
            'id': t.id,
            'title': t.title,
            'subject': t.subject,
            'period': t.period,
            'priority': t.priority,
            'dueDate': t.due_date.strftime('%Y-%m-%d'),
            'completed': t.completed,
        })
    return render(request, 'main/tasks.html', {'tasks_data': json.dumps(tasks_data)})


@login_required
@require_POST
def add_task(request):
    try:
        data     = json.loads(request.body)
        due_date = datetime.strptime(data['dueDate'], '%Y-%m-%d').date()
        task     = Task.objects.create(
            user      = request.user,
            title     = data['title'],
            subject   = data.get('subject', 'General'),
            period    = data.get('period', 'General'),
            priority  = data['priority'],
            due_date  = due_date,
            completed = False,
        )
        return JsonResponse({'status': 'success', 'task': {
            'id':        task.id,
            'title':     task.title,
            'subject':   task.subject,
            'period':    task.period,
            'priority':  task.priority,
            'dueDate':   task.due_date.strftime('%Y-%m-%d'),
            'completed': task.completed,
        }})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def edit_task(request, task_id):
    try:
        data     = json.loads(request.body)
        task     = Task.objects.get(id=task_id, user=request.user)
        due_date = datetime.strptime(data['dueDate'], '%Y-%m-%d').date()
        task.title    = data['title']
        task.subject  = data.get('subject', task.subject)
        task.period   = data.get('period', task.period)
        task.priority = data['priority']
        task.due_date = due_date
        task.save()
        return JsonResponse({'status': 'success', 'task': {
            'id':        task.id,
            'title':     task.title,
            'subject':   task.subject,
            'period':    task.period,
            'priority':  task.priority,
            'dueDate':   task.due_date.strftime('%Y-%m-%d'),
            'completed': task.completed,
        }})
    except Task.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def delete_task(request, task_id):
    try:
        Task.objects.get(id=task_id, user=request.user).delete()
        return JsonResponse({'status': 'success'})
    except Task.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)


@login_required
@require_POST
def toggle_task(request, task_id):
    try:
        task = Task.objects.get(id=task_id, user=request.user)
        task.completed = not task.completed
        task.save()
        return JsonResponse({'status': 'success', 'completed': task.completed})
    except Task.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)


@login_required
@csrf_protect
def profile(request):
    """
    User profile viewing level and academic success metrics.
    Supports POST for editing profile data.
    """
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