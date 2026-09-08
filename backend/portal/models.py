from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.crypto import get_random_string
import random
import string

class User(AbstractUser):
    BRANCH_CHOICES = (
        ('CE', 'Computer Engineering'), ('IT', 'Information Technology'),
        ('AIML', 'AI & Machine Learning'), ('ME', 'Mechanical Engineering'), ('EC', 'Electronics & Communication'),
    )
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('faculty', 'Faculty'),
        ('student', 'Student'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='student')
    enrollment_no = models.CharField(max_length=30, unique=True, null=True, blank=True)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)
    branch = models.CharField(max_length=10, choices=BRANCH_CHOICES, blank=True)
    # Comma-separated canonical subject names assigned by an administrator.
    # Kept as a simple field so existing deployments can migrate without a
    # separate subject catalogue.
    faculty_subjects = models.CharField(max_length=500, blank=True)

    # Unfair-means lock: set the moment a student blows through max proctoring
    # violations. A blocked account cannot log back in to the portal at all
    # (not just the exam) until a faculty member explicitly clears it.
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.CharField(max_length=255, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False, help_text='User must create a new password before portal access.')

    def __str__(self):
        if self.enrollment_no:
            return f"{self.name} ({self.enrollment_no})"
        return f"{self.name} ({self.username})"


def _exam_content_is_locked(exam):
    # Model-level protection uses the explicit immutable-paper flag. The API
    # sets this flag at publish time and the migration backfills active exams.
    return bool(getattr(exam, 'content_locked', False))


def _raise_if_locked(exam):
    if _exam_content_is_locked(exam):
        raise ValidationError(
            'This exam has already been published; questions, coding problems, and reference solutions are locked.'
        )



class Exam(models.Model):
    PHASE_CHOICES = (
        ('T1', 'Test 1'),
        ('T2', 'Test 2'),
        ('T3', 'Test 3'),
        ('T4', 'Test 4'),
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=120, blank=True)
    AUDIENCE_CHOICES = (('all', 'All Students'), ('department', 'Department Only'))
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default='all')
    target_department = models.CharField(max_length=100, blank=True)
    # New branch-scoped audience. target_department remains for old records.
    target_branch = models.CharField(max_length=10, choices=User.BRANCH_CHOICES, blank=True)
    phase = models.CharField(max_length=10, choices=PHASE_CHOICES, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_exams')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    passing_marks = models.FloatField(default=40.0)
    total_marks = models.FloatField(default=100.0)
    is_active = models.BooleanField(default=True)
    # Once faculty publishes, the question paper is sealed: MCQs, coding
    # problems, and reference solutions cannot change.
    content_locked = models.BooleanField(default=False)
    # Results are deliberately not released automatically at end_time. Faculty
    # must verify every attempted submission, then explicitly publish results.
    results_published = models.BooleanField(default=False)
    results_published_at = models.DateTimeField(null=True, blank=True)
    requires_otp = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ---- Proctoring / anti-cheat configuration ----
    enforce_fullscreen = models.BooleanField(default=True)
    block_shortcuts = models.BooleanField(default=True)
    block_copy_paste = models.BooleanField(default=True)
    require_screen_recording = models.BooleanField(default=True, help_text="Student must share their entire screen to enter the exam room")
    max_violations = models.IntegerField(default=3, help_text="Auto-submit after this many violations. 0 = unlimited")
    auto_submit_on_violation = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    def is_exam_active(self):
        now = timezone.now()
        allocated = float(
            sum(q.marks for q in self.mcq_questions.all()) +
            sum(p.marks for p in self.coding_problems.all())
        )
        marks_complete = allocated > 0 and abs(allocated - float(self.total_marks or 0)) <= 0.001
        return self.is_active and marks_complete and self.start_time <= now < self.end_time

    @property
    def results_released(self):
        """True only after faculty explicitly publishes results.

        Closing the exam window is not enough. Every attempted submission must
        be verified by faculty, then Publish Results releases marks to students.
        """
        return bool(self.results_published)


class StudentExamAccess(models.Model):
    """
    Temporary OTP / Password generated only for exam time.
    Will be cleared / deactivated after the exam finishes.
    """
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='access_tokens')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_accesses')
    temp_otp = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('exam', 'student')

    def __str__(self):
        return f"{self.student.enrollment_no} - {self.exam.title} - OTP: {self.temp_otp if self.is_active else 'CLEARED'}"

    @classmethod
    def generate_otp(cls, length=6):
        return ''.join(random.choices(string.digits, k=length))


class MCQQuestion(models.Model):
    OPTION_CHOICES = (
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D'),
    )
    QUESTION_TYPE_CHOICES = (
        ('single', 'Single Correct Answer'),
        ('multi', 'Multiple Correct Answers'),
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='mcq_questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE_CHOICES, default='single')
    # 'single' questions use correct_option; 'multi' questions use correct_options.
    correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES, blank=True)
    correct_options = models.JSONField(default=list, blank=True, help_text="Used when question_type='multi', e.g. ['A','C']")
    marks = models.FloatField(default=2.0)
    negative_marks = models.FloatField(default=0.0)

    def save(self, *args, **kwargs):
        if self.exam_id:
            exam = self.exam if hasattr(self, 'exam') else Exam.objects.get(id=self.exam_id)
            _raise_if_locked(exam)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.exam_id:
            exam = self.exam if hasattr(self, 'exam') else Exam.objects.get(id=self.exam_id)
            _raise_if_locked(exam)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"MCQ: {self.question_text[:50]}..."

    def correct_set(self):
        if self.question_type == 'multi':
            return set(self.correct_options or [])
        return {self.correct_option} if self.correct_option else set()


class CodingProblem(models.Model):
    LANGUAGE_CHOICES = (
        ('python', 'Python 3'),
        ('javascript', 'JavaScript (Node.js)'),
        ('cpp', 'C++'),
        ('java', 'Java'),
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='coding_problems')
    title = models.CharField(max_length=200)
    problem_statement = models.TextField()
    input_format = models.TextField(blank=True)
    output_format = models.TextField(blank=True)
    sample_input = models.TextField(blank=True)
    sample_output = models.TextField(blank=True)
    marks = models.FloatField(default=20.0)
    # Fixed at creation — the whole point is that faculty picks ONE language
    # per problem, and the student's exam compiler is locked to it.
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='python')

    def save(self, *args, **kwargs):
        if self.exam_id:
            exam = self.exam if hasattr(self, 'exam') else Exam.objects.get(id=self.exam_id)
            _raise_if_locked(exam)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.exam_id:
            exam = self.exam if hasattr(self, 'exam') else Exam.objects.get(id=self.exam_id)
            _raise_if_locked(exam)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.title


class CodingTestCase(models.Model):
    """Input/output tests used as the primary grading signal for coding problems."""
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField(blank=True)
    expected_output = models.TextField()
    is_hidden = models.BooleanField(default=True)
    weight = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        if self.problem_id:
            problem = self.problem if hasattr(self, 'problem') else CodingProblem.objects.select_related('exam').get(id=self.problem_id)
            _raise_if_locked(problem.exam)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.problem_id:
            problem = self.problem if hasattr(self, 'problem') else CodingProblem.objects.select_related('exam').get(id=self.problem_id)
            _raise_if_locked(problem.exam)
        return super().delete(*args, **kwargs)

    def __str__(self):
        vis = 'hidden' if self.is_hidden else 'visible'
        return f"{self.problem.title} - {vis} test #{self.id}"


class ReferenceSolution(models.Model):
    """
    Faculty uploads 2-3 reference answers for coding problems.
    Shown to students after evaluation if their logic is incorrect.
    """
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE, related_name='reference_solutions')
    title = models.CharField(max_length=200, help_text="e.g. Solution 1: Optimal Hash Map Approach O(N)")
    language = models.CharField(max_length=50, default='python')
    code = models.TextField()
    logic_explanation = models.TextField(help_text="Detailed explanation of the solution logic")

    def save(self, *args, **kwargs):
        if self.problem_id:
            problem = self.problem if hasattr(self, 'problem') else CodingProblem.objects.select_related('exam').get(id=self.problem_id)
            _raise_if_locked(problem.exam)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.problem_id:
            problem = self.problem if hasattr(self, 'problem') else CodingProblem.objects.select_related('exam').get(id=self.problem_id)
            _raise_if_locked(problem.exam)
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.problem.title} - {self.title}"


class StudentExamSession(models.Model):
    STATUS_CHOICES = (
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('evaluated', 'Evaluated'),
        ('ufm', 'Unfair Means — Voided'),
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='sessions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    mcq_score = models.FloatField(default=0.0)
    coding_score = models.FloatField(default=0.0)
    total_score = models.FloatField(default=0.0)
    is_passed = models.BooleanField(default=False)
    shuffled_mcq_order = models.JSONField(default=list, blank=True)
    shuffled_options = models.JSONField(default=dict, blank=True)

    # Draft auto-save (so a refresh / disconnect never loses work)
    mcq_draft = models.JSONField(default=dict, blank=True)
    coding_draft = models.JSONField(default=dict, blank=True)
    last_autosave_at = models.DateTimeField(null=True, blank=True)

    # Proctoring
    violation_count = models.IntegerField(default=0)
    is_auto_submitted = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_ufm = models.BooleanField(default=False, help_text="True once max proctoring violations were exceeded — marks voided to zero")
    ufm_reason = models.CharField(max_length=255, blank=True)

    # Faculty result verification gate. Results are publishable only after each
    # attempted/submitted session has been reviewed or explicitly verified.
    faculty_verified = models.BooleanField(default=False)
    faculty_verified_at = models.DateTimeField(null=True, blank=True)
    faculty_verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_exam_sessions'
    )

    class Meta:
        unique_together = ('exam', 'student')

    @property
    def deadline(self):
        from datetime import timedelta
        by_duration = self.started_at + timedelta(minutes=self.exam.duration_minutes)
        return min(by_duration, self.exam.end_time)

    def remaining_seconds(self):
        delta = (self.deadline - timezone.now()).total_seconds()
        return max(0, int(delta))

    def __str__(self):
        return f"{self.student.name} - {self.exam.title} ({self.status})"


class MCQResponse(models.Model):
    session = models.ForeignKey(StudentExamSession, on_delete=models.CASCADE, related_name='mcq_responses')
    question = models.ForeignKey(MCQQuestion, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1, null=True, blank=True)
    selected_options = models.JSONField(default=list, blank=True, help_text="Used for multi-select questions")
    is_correct = models.BooleanField(default=False)
    marks_awarded = models.FloatField(default=0.0)
    marks_overridden = models.BooleanField(default=False)

    class Meta:
        unique_together = ('session', 'question')


class CodingSubmission(models.Model):
    LOGIC_STATUS_CHOICES = (
        ('pending', 'Pending Evaluation'),
        ('correct', 'Correct Logic'),
        ('partial', 'Partially Correct Logic'),
        ('incorrect', 'Incorrect Logic'),
    )
    session = models.ForeignKey(StudentExamSession, on_delete=models.CASCADE, related_name='coding_submissions')
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE)
    language = models.CharField(max_length=50, default='python')
    submitted_code = models.TextField()
    logic_status = models.CharField(max_length=20, choices=LOGIC_STATUS_CHOICES, default='pending')
    marks_awarded = models.FloatField(default=0.0)
    faculty_feedback = models.TextField(blank=True)
    matched_reference = models.CharField(max_length=200, blank=True)
    reviewed_by_faculty = models.BooleanField(default=False)
    marks_overridden = models.BooleanField(default=False)
    evaluated_by = models.CharField(max_length=50, default='gemini-unavailable', help_text="Evaluator source such as gemini:<model>, gemini-unavailable, or manual review")

    # Hybrid judge / AI-debug metadata. Hidden test inputs are never stored here;
    # only visible failed cases and hidden-failure counts are retained.
    test_passed_count = models.IntegerField(default=0)
    test_total_count = models.IntegerField(default=0)
    hidden_failed_count = models.IntegerField(default=0)
    failed_visible_tests = models.JSONField(default=list, blank=True)
    ai_detected_approach = models.CharField(max_length=255, blank=True)
    ai_logic_summary = models.TextField(blank=True)
    ai_mistake_explanation = models.TextField(blank=True)
    ai_corrected_code = models.TextField(blank=True)
    ai_predicted_output = models.TextField(blank=True)
    ai_debug_source = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = ('session', 'problem')

    def __str__(self):
        return f"{self.session.student.enrollment_no} - {self.problem.title} ({self.logic_status})"


# ============================================================
#  NOTES MODULE
# ============================================================

class FacultyNote(models.Model):
    """
    Study material / notes uploaded by faculty and shared with students.
    Supports rich text body + optional file attachment + optional external link.
    """
    VISIBILITY_CHOICES = (
        ('all', 'All Students'),
        ('department', 'Department Only'),
        ('exam', 'Exam Candidates Only'),
    )

    title = models.CharField(max_length=250)
    subject = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True, help_text="Full note body / study material text")
    attachment = models.FileField(upload_to='faculty_notes/', null=True, blank=True)
    external_link = models.URLField(blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='all')
    department = models.CharField(max_length=100, blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    is_published = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_notes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.subject})"

    def visible_to(self, user):
        if user.user_type == 'faculty':
            return True
        if not self.is_published:
            return False
        if self.visibility == 'all':
            return True
        if self.visibility == 'department':
            return (self.department or '').strip().lower() == (user.department or '').strip().lower()
        if self.visibility == 'exam' and self.exam_id:
            return StudentExamAccess.objects.filter(exam_id=self.exam_id, student=user).exists()
        return False


class StudentNote(models.Model):
    """
    A student's own private notes. Never visible to anyone else.
    """
    COLOR_CHOICES = (
        ('slate', 'Slate'),
        ('blue', 'Blue'),
        ('emerald', 'Emerald'),
        ('amber', 'Amber'),
        ('rose', 'Rose'),
        ('violet', 'Violet'),
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_notes')
    title = models.CharField(max_length=250)
    content = models.TextField(blank=True)
    subject = models.CharField(max_length=120, blank=True)
    tags = models.CharField(max_length=250, blank=True, help_text="Comma separated tags")
    attachment = models.FileField(upload_to='student_notes/', null=True, blank=True)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='slate')
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-updated_at']

    def __str__(self):
        return f"{self.student.enrollment_no} - {self.title}"

    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]


class ProctorEvent(models.Model):
    """
    Anti-cheat audit trail. Logged whenever the exam room detects a violation
    (fullscreen exit, tab switch, blocked shortcut, copy/paste, right-click...).
    """
    EVENT_CHOICES = (
        ('fullscreen_exit', 'Fullscreen Exited'),
        ('tab_switch', 'Tab / Window Switch'),
        ('blur', 'Window Lost Focus'),
        ('blocked_key', 'Blocked Shortcut Key'),
        ('copy', 'Copy Attempt'),
        ('paste', 'Paste Attempt'),
        ('cut', 'Cut Attempt'),
        ('contextmenu', 'Right Click'),
        ('devtools', 'DevTools Suspected'),
        ('resize', 'Suspicious Window Resize'),
        ('auto_submit', 'Auto Submitted'),
        ('other', 'Other'),
    )
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    )

    session = models.ForeignKey(StudentExamSession, on_delete=models.CASCADE, related_name='proctor_events')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, default='other')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    details = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.session.student.enrollment_no} - {self.event_type}"


class ProctorRecording(models.Model):
    """
    Short screen-recording clips uploaded when a serious proctoring event
    occurs. Browsers require screen-capture consent at exam start; clips are
    tied to the student's session and visible only to faculty.
    """
    session = models.ForeignKey(StudentExamSession, on_delete=models.CASCADE, related_name='screen_recordings')
    event_type = models.CharField(max_length=30, default='other')
    details = models.CharField(max_length=500, blank=True)
    clip = models.FileField(upload_to='proctor_recordings/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.session.student.enrollment_no} - recording - {self.event_type}"


# ============================================================
#  PRODUCT OPERATIONS: AUDIT, NOTIFICATIONS & SELF-SERVICE
# ============================================================

class AuditLog(models.Model):
    """Immutable record for security- and marks-sensitive operations."""
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['action', '-created_at']), models.Index(fields=['actor', '-created_at'])]


class Notification(models.Model):
    TYPE_CHOICES = (
        ('exam', 'Exam'), ('result', 'Result'), ('proctor', 'Proctoring'),
        ('appeal', 'Appeal'), ('system', 'System'),
    )
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read', '-created_at'])]


def generate_reset_token():
    return get_random_string(64)


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=96, unique=True, default=generate_reset_token)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()


class QuestionBankItem(models.Model):
    """Faculty-owned reusable MCQ or coding question, independent of an exam."""
    KIND_CHOICES = (('mcq', 'MCQ'), ('coding', 'Coding'))
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='question_bank_items')
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=120, blank=True)
    tags = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['owner', 'kind', '-updated_at'])]


class ExamAppeal(models.Model):
    STATUS_CHOICES = (('open', 'Open'), ('reviewing', 'Reviewing'), ('resolved', 'Resolved'), ('rejected', 'Rejected'))
    session = models.ForeignKey(StudentExamSession, on_delete=models.CASCADE, related_name='appeals')
    question_type = models.CharField(max_length=12, choices=(('mcq', 'MCQ'), ('coding', 'Coding')), blank=True)
    question_id = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='open')
    faculty_response = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_appeals')
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['session', 'status'])]


class PracticeQuestion(models.Model):
    """A standalone MCQ used only by the ungraded, unproctored Mock Test
    page. Deliberately independent of Exam/StudentExamSession — practice
    attempts are stateless and never touch real exam or proctoring data."""
    OPTION_CHOICES = (('A', 'Option A'), ('B', 'Option B'), ('C', 'Option C'), ('D', 'Option D'))
    DIFFICULTY_CHOICES = (('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard'))
    topic = models.CharField(max_length=80)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES)
    explanation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['topic', 'id']
        indexes = [models.Index(fields=['is_active', 'topic'])]

    def __str__(self):
        return self.question_text[:60]
