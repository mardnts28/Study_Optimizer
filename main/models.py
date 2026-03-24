from django.db import models
from django.contrib.auth.models import User

class Task(models.Model):
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]
    PERIOD_CHOICES = [
        ('General', 'General'),
        ('Prelims', 'Prelims'),
        ('Midterms', 'Midterms'),
        ('Finals', 'Finals'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100, default='General')
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='General')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES)
    due_date = models.DateField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['completed', 'due_date']

class SharedMaterial(models.Model):
    PERIOD_CHOICES = [
        ('General', 'General'),
        ('Prelims', 'Prelims'),
        ('Midterms', 'Midterms'),
        ('Finals', 'Finals'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_materials')
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100)
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='General')
    content = models.TextField()
    likes = models.ManyToManyField(User, related_name='liked_materials', blank=True)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    emoji = models.CharField(max_length=10, default='📄')

    def __str__(self):
        return self.title

    @property
    def likes_count(self):
        return self.likes.count()

class Comment(models.Model):
    material = models.ForeignKey(SharedMaterial, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author.username} on {self.material.title}"

class SummarizedDocument(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='summaries')
    file_name = models.CharField(max_length=255)
    period = models.CharField(max_length=20, default='General')
    subject = models.CharField(max_length=100, default='General')
    summary_text = models.TextField()
    emoji = models.CharField(max_length=10, default='📄')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name

class ScheduleItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedule_items')
    day = models.CharField(max_length=20)
    time = models.CharField(max_length=50)
    activity = models.CharField(max_length=255)
    color = models.CharField(max_length=20, default='blue')

    def __str__(self):
        return f"{self.day}: {self.activity}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True, default="No bio yet... ✍️")
    major = models.CharField(max_length=100, blank=True, default="General Studies 🎓")
    location = models.CharField(max_length=100, blank=True, default="Focus Room 📚")

    def __str__(self):
        return f"{self.user.username}'s Profile"
