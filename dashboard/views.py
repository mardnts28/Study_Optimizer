from django.shortcuts import render

def dashboard(request):
    stats = [
    {'label': 'Documents', 'value': '24', 'change': '+3 this week', 'emoji': '📄', 'color_class': 'text-red-800'},
    {'label': 'Tasks Done', 'value': '18/25', 'change': '72% complete', 'emoji': '✅', 'color_class': 'text-emerald-500'},
    {'label': 'Study Hours', 'value': '42h', 'change': '+8h this week', 'emoji': '⏰', 'color_class': 'text-amber-500'},
    {'label': 'Progress', 'value': '76%', 'change': 'Keep it up!', 'emoji': '📈', 'color_class': 'text-violet-500'},
    ]

    weekly_data = [
        {'day': 'Mon', 'hours': 6, 'goal': 7},
        {'day': 'Tue', 'hours': 5, 'goal': 7},
        {'day': 'Wed', 'hours': 8, 'goal': 7},
        {'day': 'Thu', 'hours': 7, 'goal': 7},
        {'day': 'Fri', 'hours': 6, 'goal': 7},
        {'day': 'Sat', 'hours': 5, 'goal': 7},
        {'day': 'Sun', 'hours': 5, 'goal': 7},
    ]

    period_data = [
    {'name': 'Prelims',  'value': 90, 'tasks': '12/15', 'icon': '📝', 'bar_style': 'width:90%;background-color:#8C1007'},
    {'name': 'Midterms', 'value': 67, 'tasks': '8/12',  'icon': '📚', 'bar_style': 'width:67%;background-color:#660B05'},
    {'name': 'Finals',   'value': 33, 'tasks': '5/15',  'icon': '🎓', 'bar_style': 'width:33%;background-color:#B91C1C'},
    ]

    upcoming_tasks = [
        {'title': 'Database Final Exam', 'date': 'Mar 8', 'priority': 'High', 'days_left': 3},
        {'title': 'Algorithm Assignment', 'date': 'Mar 10', 'priority': 'High', 'days_left': 5},
        {'title': 'Physics Lab Report', 'date': 'Mar 12', 'priority': 'Medium', 'days_left': 7},
        {'title': 'Math Problem Set', 'date': 'Mar 15', 'priority': 'Low', 'days_left': 10},
    ]

    recent_activity = [
        {'title': 'Introduction to Algorithms.pdf', 'type': 'Summarized', 'time': '2 hours ago', 'emoji': '🤖'},
        {'title': 'Study for Database Quiz', 'type': 'Completed', 'time': '5 hours ago', 'emoji': '✅'},
        {'title': 'Data Structures Lecture.pptx', 'type': 'Summarized', 'time': '1 day ago', 'emoji': '📊'},
        {'title': 'Review Chapter 5', 'type': 'Started', 'time': '1 day ago', 'emoji': '📖'},
    ]

    achievements = [
    {'title': '7-Day Streak', 'emoji': '🔥', 'unlocked': True,  'progress': 100, 'progress_style': 'width:100%'},
    {'title': 'Early Bird',   'emoji': '🐦', 'unlocked': True,  'progress': 100, 'progress_style': 'width:100%'},
    {'title': 'Task Master',  'emoji': '🏆', 'unlocked': False, 'progress': 72,  'progress_style': 'width:72%'},
    {'title': 'Speed Reader', 'emoji': '⚡', 'unlocked': False, 'progress': 45,  'progress_style': 'width:45%'},
    ]

    context = {
        'stats': stats,
        'weekly_data': weekly_data,
        'period_data': period_data,
        'upcoming_tasks': upcoming_tasks,
        'recent_activity': recent_activity,
        'achievements': achievements,
        'user_name': 'John',
        'today': 'Thursday, March 5, 2026',
    }
    return render(request, 'dashboard/dashboard.html', context)


def schedule(request):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    return render(request, 'dashboard/schedule.html', {'days': days})


def alerts(request):
    alerts_list = [
        {'title': 'Database Final Exam', 'message': 'Due in 3 days - Mar 8', 'type': 'danger', 'emoji': '⚠️'},
        {'title': 'Algorithm Assignment', 'message': 'Due in 5 days - Mar 10', 'type': 'warning', 'emoji': '📝'},
        {'title': 'Great Progress!', 'message': "You've completed 72% of your tasks", 'type': 'success', 'emoji': '🎉'},
    ]
    return render(request, 'dashboard/alerts.html', {'alerts': alerts_list})

from django.shortcuts import render

def upload(request):
    summary = None
    selected_file = None
    period = ''
    error = None

    recent_summaries = [
        {'id': 1, 'title': 'Introduction to Algorithms', 'period': 'Midterms', 'date': 'Today',      'emoji': '🤖'},
        {'id': 2, 'title': 'Database Management Notes',  'period': 'Prelims',  'date': 'Yesterday',  'emoji': '💾'},
        {'id': 3, 'title': 'Data Structures Lecture',    'period': 'Midterms', 'date': '2 days ago', 'emoji': '📊'},
        {'id': 4, 'title': 'Machine Learning Basics',    'period': 'Finals',   'date': '3 days ago', 'emoji': '🧠'},
    ]

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        period = request.POST.get('period', '')

        if not uploaded_file:
            error = 'Please select a file.'
        elif not period:
            error = 'Please select an academic period.'
        else:
            selected_file = {
                'name': uploaded_file.name,
                'size': round(uploaded_file.size / 1024, 1),
            }
            # Placeholder summary — replace with real AI logic later
            summary = (
                'This document covers fundamental algorithms and data structures. '
                'Key topics include sorting algorithms (quicksort, mergesort), '
                'binary search trees with O(log n) operations, and graph traversal '
                'methods (BFS, DFS). The material emphasizes time complexity analysis '
                'and practical implementation strategies for efficient problem-solving.'
            )

    context = {
        'summary': summary,
        'selected_file': selected_file,
        'period': period,
        'error': error,
        'recent_summaries': recent_summaries,
    }
    return render(request, 'dashboard/upload.html', context)