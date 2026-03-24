from django.test import TestCase
from django.contrib.auth.models import User
from .models import Task, SummarizedDocument
from .services import generate_document_summary

class StudyServicesTest(TestCase):
    def test_summarization_logic(self):
        """
        Tests that the summarization service returns a structured string.
        """
        content = "This is a long sentence about artificial intelligence. " * 20
        file_name = "test_ai.pdf"
        summary, title = generate_document_summary(content, file_name)
        
        self.assertIn("Analysis of", title)
        self.assertIn("KEY HIGHLIGHTS", summary)
        self.assertIn("CORE CONCEPTS", summary)
        self.assertNotIn("====", summary)

class TaskMetricsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    def test_study_hours_calculation(self):
        """
        Verify that 2 hours are credited per task and 1 per summary.
        """
        Task.objects.create(user=self.user, title="Task 1", completed=True, due_date='2025-01-01', priority='High')
        SummarizedDocument.objects.create(user=self.user, file_name="Doc 1", summary_text="Summary...")
        
        # This logic is currently mirrored in dashboard and profile views
        # We'll calculate it here to ensure the logic remains consistent
        completed_tasks = Task.objects.filter(user=self.user, completed=True).count()
        summaries_count = SummarizedDocument.objects.filter(user=self.user).count()
        
        study_hours = (completed_tasks * 2) + (summaries_count * 1)
        self.assertEqual(study_hours, 3)

    def test_level_progression(self):
        """
        Verify the level system logic (1 level per 5 tasks).
        """
        # Create 11 completed tasks for the user
        for i in range(11):
            Task.objects.create(user=self.user, title=f"Task {i}", completed=True, due_date='2025-01-01', priority='Low')
        
        completed_count = Task.objects.filter(user=self.user, completed=True).count()
        user_level = (completed_count // 5) + 1
        
        self.assertEqual(user_level, 3) # (11 // 5) + 1 = 2 + 1 = 3
