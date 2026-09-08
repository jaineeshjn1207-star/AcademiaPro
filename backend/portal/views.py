from rest_framework import viewsets, status, views, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import PermissionDenied
from django.db import transaction, IntegrityError
from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count, Sum
import random
import re
import csv
import io
import threading
from datetime import timedelta, timezone as dt_timezone
from django.utils.crypto import get_random_string

from .models import (
    User, Exam, StudentExamAccess, MCQQuestion, CodingProblem,
    ReferenceSolution, StudentExamSession, MCQResponse, CodingSubmission,
    FacultyNote, StudentNote, ProctorEvent, ProctorRecording, AuditLog,
    Notification, PasswordResetToken, QuestionBankItem, ExamAppeal, PracticeQuestion
)
try:
    from .charts import generate_analytics_charts as _generate_analytics_charts
except Exception:  # Chart rendering is optional (matplotlib/seaborn may be missing in a minimal env).
    _generate_analytics_charts = None

def generate_analytics_charts(exam_id, analytics_data):
    if _generate_analytics_charts is None:
        return {}
    try:
        return _generate_analytics_charts(exam_id, analytics_data)
    except Exception:
        # Analytics data should never fail just because server-side image rendering failed.
        return {}
from .ai_code_evaluator import evaluate_code_ai_first
from .code_runner import run_code
from .serializers import (
    UserSerializer, ExamSerializer, StudentExamAccessSerializer,
    MCQQuestionStudentSerializer, MCQQuestionFacultySerializer,
    CodingProblemStudentSerializer, CodingProblemFacultySerializer,
    ReferenceSolutionSerializer, StudentExamSessionSerializer,
    CodingSubmissionSerializer, MCQResponseSerializer,
    FacultyNoteSerializer, StudentNoteSerializer, ProctorEventSerializer,
    ProctorRecordingSerializer
)
from .permissions import IsFaculty, IsStudent, IsAdmin, BLOCKED_MESSAGE


def request_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


def audit(request, action, target=None, details=None):
    """Never let an audit-write failure interrupt the protected action."""
    try:
        AuditLog.objects.create(
            actor=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
            action=action,
            target_type=target.__class__.__name__ if target is not None else '',
            target_id=str(getattr(target, 'pk', '') or ''),
            details=details or {}, ip_address=request_ip(request),
        )
    except Exception:
        pass


def notify(recipient, notification_type, title, body='', link=''):
    return Notification.objects.create(
        recipient=recipient, notification_type=notification_type,
        title=title, body=body, link=link,
    )


def faculty_can_review_exam(user, exam):
    """Whether faculty can make changes/review students for this exam."""
    if user.user_type != 'faculty':
        return False
    if exam.created_by_id == user.id:
        return True
    exam_branch = (exam.target_branch or exam.created_by.branch or '').strip().upper()
    user_branch = (user.branch or '').strip().upper()
    if not exam_branch and not user_branch:
        return True
    if not exam_branch or not user_branch:
        return False
    return exam_branch == user_branch


def faculty_can_view_exam(user, exam):
    """Faculty may view any branch; editing and student review stay branch-scoped."""
    return user.user_type == 'faculty'


def ensure_faculty_subject(user, subject):
    assigned = {item.strip().casefold() for item in (user.faculty_subjects or '').split(',') if item.strip()}
    if assigned and (subject or '').strip().casefold() not in assigned:
        raise PermissionDenied('You can create papers only for your assigned subjects.')


def faculty_allowed_coding_languages(user):
    """Return the compiler languages explicitly assigned to a faculty user.

    Faculty subjects predate the coding editor and are stored as human-readable
    names (for example, ``C++`` and ``Java``).  Treat those programming
    subjects as the language entitlement.  An empty assignment remains
    unrestricted for backwards compatibility with existing faculty accounts.
    """
    aliases = {
        'python': 'python', 'python 3': 'python',
        'javascript': 'javascript', 'node.js': 'javascript', 'nodejs': 'javascript',
        'c++': 'cpp', 'cpp': 'cpp', 'c plus plus': 'cpp',
        'java': 'java',
    }
    subjects = [item.strip().casefold() for item in (user.faculty_subjects or '').split(',') if item.strip()]
    return {aliases[item] for item in subjects if item in aliases}


def paginate_rows(request, rows, default_size=50, max_size=200):
    """Stable page metadata for list endpoints that currently build dict rows."""
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(max(1, int(request.query_params.get('page_size', default_size))), max_size)
    except (TypeError, ValueError):
        page_size = default_size
    total = len(rows)
    page_count = max(1, (total + page_size - 1) // page_size)
    page = min(page, page_count)
    start = (page - 1) * page_size
    return rows[start:start + page_size], {
        'page': page, 'page_size': page_size, 'total': total,
        'page_count': page_count, 'has_next': page < page_count, 'has_previous': page > 1,
    }


def allocated_exam_marks(exam, exclude_mcq_id=None, exclude_problem_id=None):
    """Total marks already allocated to MCQs + coding problems for an exam."""
    mcqs = MCQQuestion.objects.filter(exam=exam)
    if exclude_mcq_id:
        mcqs = mcqs.exclude(id=exclude_mcq_id)
    problems = CodingProblem.objects.filter(exam=exam)
    if exclude_problem_id:
        problems = problems.exclude(id=exclude_problem_id)
    return float(sum(q.marks for q in mcqs) + sum(p.marks for p in problems))


def validate_exam_mark_budget(exam, new_marks, exclude_mcq_id=None, exclude_problem_id=None):
    new_marks = float(new_marks or 0)
    if new_marks <= 0:
        return False, 'Marks must be greater than zero.'
    allocated = allocated_exam_marks(exam, exclude_mcq_id, exclude_problem_id)
    total_after = allocated + new_marks
    if total_after > float(exam.total_marks or 0):
        remaining = max(0.0, float(exam.total_marks or 0) - allocated)
        return False, (
            f'Marks exceed exam total. Already allocated: {allocated:g}, '
            f'remaining: {remaining:g}, attempted new marks: {new_marks:g}, '
            f'exam total: {float(exam.total_marks or 0):g}.'
        )
    return True, ''


def exam_mark_allocation_status(exam):
    """Return (is_complete, allocated, remaining, message) for publish/start gates."""
    allocated = allocated_exam_marks(exam)
    total = float(exam.total_marks or 0)
    remaining = total - allocated
    if allocated <= 0:
        return False, allocated, remaining, 'Add questions/problems before publishing this exam.'
    if abs(remaining) > 0.001:
        if remaining > 0:
            return False, allocated, remaining, (
                f'Exam marks are incomplete. Allocated: {allocated:g}, '
                f'total: {total:g}, remaining: {remaining:g}.'
            )
        return False, allocated, remaining, (
            f'Exam marks exceed total. Allocated: {allocated:g}, total: {total:g}.'
        )
    return True, allocated, 0.0, ''


def deactivate_if_mark_budget_incomplete(exam):
    """If question edits make a published/active exam incomplete, deactivate it."""
    ok, _, _, _ = exam_mark_allocation_status(exam)
    if exam.is_active and not ok:
        exam.is_active = False
        exam.save(update_fields=['is_active'])
        return True
    return False


def content_locked_response(exam):
    # In this project, publishing an exam activates it. Treat either the
    # immutable content_locked flag OR an active/published exam as sealed.
    # This also protects deployments where an exam was already active before
    # the content_locked migration was introduced.
    if getattr(exam, 'content_locked', False) or getattr(exam, 'is_active', False):
        return Response({
            'error': 'This exam has already been published, so its questions, coding problems, reference solutions, and legacy test-case rows are locked.'
        }, status=status.HTTP_400_BAD_REQUEST)
    return None


def flatten_coding_answer(sub_data):
    """Return a grading-friendly text answer from either a legacy single-file
    payload or the IDE-style multi-file workspace payload.

    The database still stores one TextField (`submitted_code`) so older faculty
    review screens, exports and Gemini evaluation keep working.  When the
    frontend sends `files`, we serialize each file with a clear path separator.
    If a legacy client sends only `code`, that value is used unchanged.
    """
    if not isinstance(sub_data, dict):
        return str(sub_data or '')

    files = sub_data.get('files')
    if isinstance(files, list):
        sections = []
        for item in sorted(files, key=lambda x: str((x or {}).get('path', ''))):
            if not isinstance(item, dict) or item.get('type') == 'folder':
                continue
            path = str(item.get('path', '') or '').strip().replace('\\', '/')
            path = path.strip('/') or 'untitled.txt'
            content = str(item.get('content', '') or '')
            sections.append(f"===== FILE: {path} =====\n{content}")
        flattened = '\n\n'.join(sections).strip()
        if flattened:
            return flattened

    return str(sub_data.get('code', '') or '')


def registered_exam_students(exam):
    """Students actually eligible for OTPs/access on this exam.

    Excludes accounts with no enrollment number (e.g. an admin/faculty login
    that defaulted to user_type='student') and, for a department-scoped exam,
    students outside the target branch. This is the single source of truth
    for "who should have an OTP for this exam" — used both by automatic OTP
    creation (on exam create/publish) and the manual Generate button, so a
    stray/ineligible access row can't linger from one path while the other
    was fixed.
    """
    students = User.objects.filter(user_type='student').exclude(
        Q(enrollment_no__isnull=True) | Q(enrollment_no='')
    )
    if exam.audience == 'department' and exam.target_branch:
        students = students.filter(branch=exam.target_branch)
    return students


def auto_generate_exam_otps(exam, reset_existing=False):
    """Create temporary OTP rows for every registered, eligible student.

    Called automatically when an exam is first created and again when it is
    published. Creation gives faculty the OTP list immediately in the OTP tab;
    publishing ensures any students added later also receive an active OTP.

    reset_existing=False keeps already-issued active OTPs stable, so publishing
    does not surprise faculty/students by changing codes they may already have.
    The manual OTP button still regenerates all codes.

    Also clears out any access row for a student who is no longer eligible
    (deleted, no enrollment number, or moved out of a department-only exam's
    target branch) so it stops showing up as a live/active OTP.
    """
    generated = []
    students = registered_exam_students(exam)
    eligible_ids = set(students.values_list('id', flat=True))
    StudentExamAccess.objects.filter(exam=exam).exclude(student_id__in=eligible_ids).delete()
    for student in students:
        try:
            with transaction.atomic():
                access, _ = StudentExamAccess.objects.get_or_create(exam=exam, student=student)
        except IntegrityError:
            access = StudentExamAccess.objects.get(exam=exam, student=student)

        if reset_existing or not access.temp_otp or not access.is_active:
            access.temp_otp = StudentExamAccess.generate_otp(6)
        access.is_active = True
        access.cleared_at = None
        access.save(update_fields=['temp_otp', 'is_active', 'cleared_at'])
        generated.append(access)
    return generated


def result_publication_status(exam):
    """Return result publish readiness for attempted sessions."""
    sessions = StudentExamSession.objects.filter(
        exam=exam,
        status__in=['submitted', 'evaluated', 'ufm'],
    )
    total = sessions.count()
    verified = sessions.filter(faculty_verified=True).count()
    unverified = total - verified
    in_progress = StudentExamSession.objects.filter(exam=exam, status='in_progress').count()
    return {
        'total_attempted': total,
        'verified': verified,
        'unverified': unverified,
        'in_progress': in_progress,
        'can_publish_results': (
            total > 0 and unverified == 0 and in_progress == 0 and timezone.now() >= exam.end_time
        ),
        'results_published': bool(exam.results_published),
        'results_published_at': exam.results_published_at,
    }


def mark_session_verified(session, faculty):
    session.faculty_verified = True
    session.faculty_verified_at = timezone.now()
    session.faculty_verified_by = faculty
    session.save(update_fields=['faculty_verified', 'faculty_verified_at', 'faculty_verified_by'])
    return session



class LoginRateThrottle(SimpleRateThrottle):
    """Throttle login attempts per (IP, submitted username) pair.

    A plain IP-based throttle punishes an entire campus network: students on
    the same WiFi/NAT share one public IP, so a handful of legitimate logins
    around exam start would exhaust the IP's whole quota and lock everyone
    else out. Keying on IP + attempted username still stops someone from
    brute-forcing a single account, without one student's login attempts
    affecting anyone else's.
    """
    scope = 'login'

    def get_cache_key(self, request, view):
        username = (request.data.get('username') or '').strip().lower()
        ident = f"{self.get_ident(request)}:{username}" if username else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


def gemini_evaluate_coding_submission(code, lang, problem, refs):
    """Gemini-only evaluator wrapper used by submission grading.

    Coding is scored only by Gemini. If Gemini is unavailable or invalid, the
    submission is marked pending for faculty review; no local/static/custom
    fallback is used.
    """
    verdict = evaluate_code_ai_first(code=code, language=lang, problem=problem, refs=refs)
    return verdict, verdict.get('source', 'gemini-unavailable')


def evaluate_coding_submissions_in_background(session_id):
    """Finish Gemini grading after the student's paper has been saved.

    A slow AI provider must never make a completed exam look as if it was not
    submitted.  The worker only touches still-pending, non-overridden answers,
    so a faculty review always wins if it happens first.
    """
    try:
        session = StudentExamSession.objects.select_related('exam').get(id=session_id)
        pending = (CodingSubmission.objects.filter(session=session, logic_status='pending', marks_overridden=False)
                   .select_related('problem').prefetch_related('problem__reference_solutions'))
        for submission in pending:
            problem = submission.problem
            refs = list(problem.reference_solutions.all())
            verdict, evaluated_by = gemini_evaluate_coding_submission(
                submission.submitted_code, submission.language, problem, refs
            )
            # Do not overwrite a faculty decision made while Gemini was running.
            CodingSubmission.objects.filter(id=submission.id, logic_status='pending', marks_overridden=False).update(
                logic_status=verdict['logic_status'], marks_awarded=verdict['marks_awarded'],
                faculty_feedback=verdict['feedback'], matched_reference=verdict['matched_reference'] or '',
                evaluated_by=evaluated_by,
                test_passed_count=int(verdict.get('test_passed_count', 0) or 0),
                test_total_count=int(verdict.get('test_total_count', 0) or 0),
                hidden_failed_count=int(verdict.get('hidden_failed_count', 0) or 0),
                failed_visible_tests=verdict.get('failed_visible_tests', []) or [],
                ai_detected_approach=(verdict.get('ai_debug') or {}).get('detected_approach', '')[:255],
                ai_logic_summary=(verdict.get('ai_debug') or {}).get('logic_summary', ''),
                ai_mistake_explanation=(verdict.get('ai_debug') or {}).get('mistake_explanation', ''),
                ai_corrected_code=(verdict.get('ai_debug') or {}).get('corrected_code', ''),
                ai_predicted_output=(verdict.get('ai_debug') or {}).get('predicted_output', ''),
                ai_debug_source=(verdict.get('ai_debug') or {}).get('source', ''),
            )
        session.refresh_from_db()
        coding_total = CodingSubmission.objects.filter(session=session).aggregate(total=Sum('marks_awarded'))['total'] or 0
        session.coding_score = round(float(coding_total), 2)
        session.total_score = round(session.mcq_score + session.coding_score, 2)
        session.is_passed = session.total_score >= session.exam.passing_marks
        session.status = 'evaluated'
        session.save(update_fields=['coding_score', 'total_score', 'is_passed', 'status'])
    except Exception:
        # A failed background grade remains visibly pending for faculty review;
        # the submission itself is already safely stored.
        return


def send_submission_receipt(email, exam_title, submitted_at):
    """Email is a courtesy; it must not hold up the exam submission receipt."""
    try:
        send_mail(
            f'Exam submission received: {exam_title}',
            f'Your submission for "{exam_title}" was received at {timezone.localtime(submitted_at):%d %b %Y, %H:%M}. '
            'Your result will be available once your faculty publishes it.',
            None, [email], fail_silently=True,
        )
    except Exception:
        pass


def _authenticate_any_user(username, password):
    username = (username or '').strip()
    user = authenticate(username=username, password=password)
    if not user:
        user_obj = (User.objects.filter(email__iexact=username).first()
                    or User.objects.filter(enrollment_no__iexact=username).first())
        if user_obj:
            user = authenticate(username=user_obj.username, password=password)
    return user


class UnifiedLoginView(views.APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = _authenticate_any_user(username, password)
        if not user:
            return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)
        if user.user_type == 'student' and user.is_blocked:
            reason = f" Reason on file: {user.blocked_reason}" if user.blocked_reason else ""
            return Response({'error': f"{BLOCKED_MESSAGE.split(': ', 1)[1]}{reason}", 'blocked': True}, status=status.HTTP_403_FORBIDDEN)
        if user.must_change_password:
            return Response({'error': 'Create a new password before signing in.', 'must_change_password': True, 'username': user.username}, status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        return Response({'refresh': str(refresh), 'access': str(refresh.access_token), 'user': UserSerializer(user).data})


class ForcePasswordChangeView(views.APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        username = request.data.get('username')
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        if not username or not current_password or not new_password:
            return Response({'error': 'username, current_password and new_password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = _authenticate_any_user(username, current_password)
        if not user:
            return Response({'error': 'Temporary/current password is incorrect.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.must_change_password:
            return Response({'error': 'This account does not require password creation.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(str(new_password)) < 8:
            return Response({'error': 'New password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(str(new_password))
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        return Response({'message': 'Password created. Please sign in with the new password.'})


class FacultyLoginView(views.APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password are required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        username = username.strip()
        user = authenticate(username=username, password=password)
        if not user:
            # Allow login with email or enrollment number too
            user_obj = (User.objects.filter(email__iexact=username).first()
                        or User.objects.filter(enrollment_no__iexact=username).first())
            if user_obj:
                user = authenticate(username=user_obj.username, password=password)

        if not user:
            return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)

        if user.user_type != 'faculty':
            return Response({'error': 'Access denied. This login is reserved for faculty members.'}, status=status.HTTP_403_FORBIDDEN)
        if user.must_change_password:
            return Response({'error': 'Create a new password before signing in.', 'must_change_password': True, 'username': user.username}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })


class StudentNormalLoginView(views.APIView):
    """Normal student login (username + permanent password) for portal access."""
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '').strip()
        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = authenticate(username=username, password=password)
        if not user:
            # Allow enrollment number lookup
            user_obj = User.objects.filter(enrollment_no__iexact=username, user_type='student').first()
            if user_obj:
                user = authenticate(username=user_obj.username, password=password)
        if not user:
            return Response({'error': 'Invalid student credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        if user.user_type != 'student':
            return Response({'error': 'Access denied. This login is for students.'}, status=status.HTTP_403_FORBIDDEN)
        if user.is_blocked:
            reason = f" Reason on file: {user.blocked_reason}" if user.blocked_reason else ""
            return Response(
                {'error': f"{BLOCKED_MESSAGE.split(': ', 1)[1]}{reason}", 'blocked': True},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.must_change_password:
            return Response({'error': 'Create a new password before signing in.', 'must_change_password': True, 'username': user.username}, status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        })


class CurrentUserView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.user_type == 'student' and user.is_blocked:
            reason = f" Reason on file: {user.blocked_reason}" if user.blocked_reason else ""
            return Response(
                {'error': f"{BLOCKED_MESSAGE.split(': ', 1)[1]}{reason}", 'blocked': True},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(UserSerializer(request.user).data)


class ExamViewSet(viewsets.ModelViewSet):
    serializer_class = ExamSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Exam.objects.all().order_by('-created_at')
        if getattr(user, 'user_type', None) == 'student':
            return qs.filter(is_active=True, access_tokens__student=user).filter(
                Q(audience='all') | Q(target_branch__iexact=user.branch)
            ).distinct()
        if getattr(user, 'user_type', None) == 'faculty':
            return qs
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsFaculty()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # New exams are saved as unpublished/inactive settings first. Faculty
        # must allocate exactly the total marks and then click Publish Exam.
        subject = str(serializer.validated_data.get('subject') or '').strip()
        ensure_faculty_subject(self.request.user, subject)
        audience = serializer.validated_data.get('audience', 'all')
        target_branch = str(serializer.validated_data.get('target_branch') or '').strip().upper()
        if audience == 'department':
            target_branch = self.request.user.branch
        exam = serializer.save(created_by=self.request.user, is_active=False, target_branch=target_branch, target_department='')
        # Temporary OTPs are available immediately in the OTP tab; students still
        # cannot start until the exam is published and the time window opens.
        auto_generate_exam_otps(exam, reset_existing=True)

    def _reject_publish_bypass(self, request):
        # Publishing must go through /publish/ so exact mark allocation is
        # checked and the paper is sealed. Do not let a generic PATCH flip
        # is_active/content_locked directly.
        if 'content_locked' in request.data:
            return Response({'error': 'content_locked is managed by Publish Exam and cannot be edited directly.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if str(request.data.get('is_active', '')).lower() in ('true', '1', 'yes'):
            return Response({'error': 'Use the Publish Exam button/API after allocating exact marks; is_active cannot be enabled directly.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return None

    def update(self, request, *args, **kwargs):
        exam = self.get_object()
        if not faculty_can_review_exam(request.user, exam):
            return Response({'error': 'Only faculty from this branch can edit this assessment.'}, status=status.HTTP_403_FORBIDDEN)
        ensure_faculty_subject(request.user, str(request.data.get('subject', exam.subject) or '').strip())
        locked = content_locked_response(exam)
        if locked:
            return locked
        bypass = self._reject_publish_bypass(request)
        if bypass:
            return bypass
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        exam = self.get_object()
        if not faculty_can_review_exam(request.user, exam):
            return Response({'error': 'Only faculty from this branch can edit this assessment.'}, status=status.HTTP_403_FORBIDDEN)
        ensure_faculty_subject(request.user, str(request.data.get('subject', exam.subject) or '').strip())
        locked = content_locked_response(exam)
        if locked:
            return locked
        bypass = self._reject_publish_bypass(request)
        if bypass:
            return bypass
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        exam = self.get_object()
        if not faculty_can_review_exam(request.user, exam):
            return Response({'error': 'Only faculty from this branch can delete this assessment.'}, status=status.HTTP_403_FORBIDDEN)
        locked = content_locked_response(exam)
        if locked:
            return locked
        return super().destroy(request, *args, **kwargs)


class FacultyExamManagementView(views.APIView):
    permission_classes = [IsFaculty]

    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        if not faculty_can_view_exam(request.user, exam):
            return Response({'error': 'This assessment is not available.'}, status=status.HTTP_403_FORBIDDEN)

        mcqs = MCQQuestion.objects.filter(exam=exam)
        coding = CodingProblem.objects.filter(exam=exam)
        # Defensive filter to match registered_exam_students: never display an
        # OTP row for an account without a real enrollment number, even if a
        # stray access row exists from an older code path.
        otps = StudentExamAccess.objects.filter(exam=exam).exclude(
            Q(student__enrollment_no__isnull=True) | Q(student__enrollment_no='')
        )

        return Response({
            'exam': ExamSerializer(exam).data,
            'mcqs': MCQQuestionFacultySerializer(mcqs, many=True).data,
            'coding_problems': CodingProblemFacultySerializer(coding, many=True).data,
            'otps': StudentExamAccessSerializer(otps, many=True).data
        })


class CreateMCQView(views.APIView):
    permission_classes = [IsFaculty]

    REQUIRED = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d']

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(exam)
        if locked:
            return locked

        data = request.data
        missing = [f for f in self.REQUIRED if not str(data.get(f, '')).strip()]
        if missing:
            return Response({'error': f"Missing required field(s): {', '.join(missing)}"},
                            status=status.HTTP_400_BAD_REQUEST)

        q_type = str(data.get('question_type', 'single')).strip().lower()
        if q_type not in ('single', 'multi'):
            return Response({'error': "question_type must be 'single' or 'multi'."},
                            status=status.HTTP_400_BAD_REQUEST)

        correct = ''
        correct_options = []
        if q_type == 'single':
            correct = str(data.get('correct_option', 'A')).strip().upper()
            if correct not in ('A', 'B', 'C', 'D'):
                return Response({'error': 'correct_option must be one of A, B, C, D.'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            raw_options = data.get('correct_options', [])
            if isinstance(raw_options, str):
                raw_options = [o.strip() for o in raw_options.split(',') if o.strip()]
            correct_options = sorted({str(o).strip().upper() for o in raw_options if str(o).strip().upper() in ('A', 'B', 'C', 'D')})
            if len(correct_options) < 2:
                return Response({'error': 'Multi-select questions need at least 2 correct options selected.'},
                                status=status.HTTP_400_BAD_REQUEST)

        try:
            marks = float(data.get('marks', 2.0))
            negative = float(data.get('negative_marks', 0.0) or 0.0)
        except (TypeError, ValueError):
            return Response({'error': 'marks / negative_marks must be numbers.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if negative < 0:
            return Response({'error': 'negative_marks cannot be negative.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ok, mark_error = validate_exam_mark_budget(exam, marks)
        if not ok:
            return Response({'error': mark_error}, status=status.HTTP_400_BAD_REQUEST)

        question = MCQQuestion.objects.create(
            exam=exam,
            question_text=str(data.get('question_text')).strip(),
            option_a=str(data.get('option_a')).strip(),
            option_b=str(data.get('option_b')).strip(),
            option_c=str(data.get('option_c')).strip(),
            option_d=str(data.get('option_d')).strip(),
            question_type=q_type,
            correct_option=correct,
            correct_options=correct_options,
            marks=marks,
            negative_marks=negative,
        )
        deactivate_if_mark_budget_incomplete(exam)
        return Response(MCQQuestionFacultySerializer(question).data, status=status.HTTP_201_CREATED)

    def patch(self, request, exam_id, mcq_id):
        q = MCQQuestion.objects.filter(id=mcq_id, exam_id=exam_id).select_related('exam').first()
        if not q:
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(q.exam)
        if locked:
            return locked
        serializer = MCQQuestionFacultySerializer(q, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if 'marks' in serializer.validated_data:
            ok, mark_error = validate_exam_mark_budget(q.exam, serializer.validated_data['marks'], exclude_mcq_id=q.id)
            if not ok:
                return Response({'error': mark_error}, status=status.HTTP_400_BAD_REQUEST)
        question = serializer.save()
        if 'marks' in serializer.validated_data:
            deactivate_if_mark_budget_incomplete(question.exam)
        return Response(serializer.data)

    def delete(self, request, exam_id, mcq_id):
        question = MCQQuestion.objects.filter(id=mcq_id, exam_id=exam_id).select_related('exam').first()
        if not question:
            return Response({'error': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)
        exam = question.exam
        locked = content_locked_response(exam)
        if locked:
            return locked
        question.delete()
        deactivate_if_mark_budget_incomplete(exam)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkMCQImportView(views.APIView):
    """Adds many MCQs to an exam at once from an uploaded CSV, so faculty
    aren't stuck adding questions one at a time in the manual form.

    Expected columns: question_text, option_a, option_b, option_c, option_d,
    correct_option, marks (optional, default 2), negative_marks (optional,
    default 0). correct_option may hold multiple letters (e.g. "A,C" or
    "AC") for a multi-select question; a single letter makes it single-select.
    Each row is validated with the exact same rules as adding one MCQ by
    hand, so a bulk import can never create a question the manual form
    would have rejected. Rows are processed independently — one bad row is
    reported and skipped rather than aborting the whole file.
    """
    permission_classes = [IsFaculty]
    parser_classes = [MultiPartParser, FormParser]
    REQUIRED = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(exam)
        if locked:
            return locked

        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'No CSV file was uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows = list(csv.DictReader(io.TextIOWrapper(upload.file, encoding='utf-8-sig')))
        except (UnicodeDecodeError, csv.Error) as error:
            return Response({'error': f'Invalid CSV: {error}'}, status=status.HTTP_400_BAD_REQUEST)

        created, errors = [], []
        for line, row in enumerate(rows, start=2):
            missing = [f for f in self.REQUIRED if not str(row.get(f, '')).strip()]
            if missing:
                errors.append({'line': line, 'error': f"Missing {', '.join(missing)}"})
                continue

            raw_correct = str(row.get('correct_option', '')).strip().upper()
            if ',' in raw_correct:
                letters = sorted({c.strip() for c in raw_correct.split(',') if c.strip()})
            else:
                letters = sorted(set(raw_correct))  # handles both "A" and concatenated "AC"
            invalid_letters = [c for c in letters if c not in ('A', 'B', 'C', 'D')]
            if not letters or invalid_letters:
                errors.append({'line': line, 'error': f'correct_option must be one or more of A/B/C/D (got "{raw_correct}").'})
                continue
            q_type = 'single' if len(letters) == 1 else 'multi'

            try:
                marks = float(row.get('marks') or 2.0)
                negative = float(row.get('negative_marks') or 0.0)
            except (TypeError, ValueError):
                errors.append({'line': line, 'error': 'marks / negative_marks must be numbers.'})
                continue
            if negative < 0:
                errors.append({'line': line, 'error': 'negative_marks cannot be negative.'})
                continue

            ok, mark_error = validate_exam_mark_budget(exam, marks)
            if not ok:
                errors.append({'line': line, 'error': mark_error})
                continue

            question = MCQQuestion.objects.create(
                exam=exam,
                question_text=str(row['question_text']).strip(),
                option_a=str(row['option_a']).strip(), option_b=str(row['option_b']).strip(),
                option_c=str(row['option_c']).strip(), option_d=str(row['option_d']).strip(),
                question_type=q_type,
                correct_option=letters[0] if q_type == 'single' else '',
                correct_options=letters if q_type == 'multi' else [],
                marks=marks, negative_marks=negative,
            )
            created.append(question.id)

        deactivate_if_mark_budget_incomplete(exam)
        audit(request, 'mcqs_bulk_imported', exam, {'created': len(created), 'errors': len(errors)})
        return Response({'created': len(created), 'errors': errors}, status=status.HTTP_200_OK)


class CreateCodingProblemView(views.APIView):
    permission_classes = [IsFaculty]

    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(exam)
        if locked:
            return locked

        data = request.data
        title = str(data.get('title', '')).strip()
        statement = str(data.get('problem_statement', '')).strip()
        if not title or not statement:
            return Response({'error': 'title and problem_statement are required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        language = str(data.get('language', 'python')).strip().lower()
        valid_languages = dict(CodingProblem.LANGUAGE_CHOICES)
        if language not in valid_languages:
            return Response({'error': f"language must be one of: {', '.join(valid_languages)}."},
                            status=status.HTTP_400_BAD_REQUEST)
        allowed_languages = faculty_allowed_coding_languages(request.user)
        if allowed_languages and language not in allowed_languages:
            return Response({'error': 'You can add coding problems only in your assigned programming language.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            marks = float(data.get('marks', 20.0))
        except (TypeError, ValueError):
            return Response({'error': 'marks must be a number.'}, status=status.HTTP_400_BAD_REQUEST)
        ok, mark_error = validate_exam_mark_budget(exam, marks)
        if not ok:
            return Response({'error': mark_error}, status=status.HTTP_400_BAD_REQUEST)

        problem = CodingProblem.objects.create(
            exam=exam,
            title=title,
            problem_statement=statement,
            input_format=data.get('input_format', ''),
            output_format=data.get('output_format', ''),
            sample_input=data.get('sample_input', ''),
            sample_output=data.get('sample_output', ''),
            marks=marks,
            language=language,
        )

        # Handle 2-3 reference solutions uploaded along with problem. A problem
        # only ever compiles/runs in one language, so every reference solution
        # is forced to that same language regardless of what was submitted —
        # there is no such thing as a mismatched-language reference solution.
        solutions_data = data.get('reference_solutions', [])
        for sol in solutions_data:
            if sol.get('title') and sol.get('code'):
                ReferenceSolution.objects.create(
                    problem=problem,
                    title=sol.get('title'),
                    language=language,
                    code=sol.get('code'),
                    logic_explanation=sol.get('logic_explanation', '')
                )


        deactivate_if_mark_budget_incomplete(exam)
        return Response(CodingProblemFacultySerializer(problem).data, status=status.HTTP_201_CREATED)

    def delete(self, request, exam_id, problem_id):
        problem = CodingProblem.objects.filter(id=problem_id, exam_id=exam_id).select_related('exam').first()
        if not problem:
            return Response({'error': 'Coding problem not found'}, status=status.HTTP_404_NOT_FOUND)
        exam = problem.exam
        locked = content_locked_response(exam)
        if locked:
            return locked
        problem.delete()
        deactivate_if_mark_budget_incomplete(exam)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GenerateOTPsView(views.APIView):
    permission_classes = [IsFaculty]

    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        student_enrollments = request.data.get('enrollments', [])
        if not student_enrollments:
            # Generate for registered students only (a real enrollment number),
            # scoped to the exam's audience so a department-only exam does not
            # hand out OTPs to every student in the portal. Also drop any
            # stale access row for a student who no longer qualifies, so it
            # can't keep showing up as a live/active OTP.
            students = registered_exam_students(exam)
            StudentExamAccess.objects.filter(exam=exam).exclude(
                student_id__in=students.values_list('id', flat=True)
            ).delete()
        else:
            students = User.objects.filter(user_type='student', enrollment_no__in=student_enrollments)

        generated_list = []
        for student in students:
            try:
                with transaction.atomic():
                    access, created = StudentExamAccess.objects.get_or_create(
                        exam=exam,
                        student=student
                    )
            except IntegrityError:
                access = StudentExamAccess.objects.get(exam=exam, student=student)
            access.temp_otp = StudentExamAccess.generate_otp(6)
            access.is_active = True
            access.cleared_at = None
            access.save()
            generated_list.append(access)
        audit(request, 'otp_regenerated', exam, {'student_count': len(generated_list)})

        return Response({
            'message': f'Generated OTPs for {len(generated_list)} students.',
            'otps': StudentExamAccessSerializer(generated_list, many=True).data
        })

    def delete(self, request, exam_id):
        """Clear all OTPs for an exam (after exam finishes)"""
        now = timezone.now()
        StudentExamAccess.objects.filter(exam_id=exam_id).update(is_active=False, cleared_at=now)
        return Response({'message': 'All OTPs cleared successfully.'})



class PublishExamView(views.APIView):
    """Publish/activate an exam only after exact mark allocation."""
    permission_classes = [IsFaculty]

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        ok, allocated, remaining, message = exam_mark_allocation_status(exam)
        if not ok:
            return Response({
                'error': f'Cannot publish exam. {message}',
                'allocated_marks': allocated,
                'remaining_marks': max(0.0, remaining),
                'total_marks': float(exam.total_marks or 0),
            }, status=status.HTTP_400_BAD_REQUEST)

        exam.is_active = True
        exam.content_locked = True
        exam.save(update_fields=['is_active', 'content_locked'])
        otps = auto_generate_exam_otps(exam, reset_existing=False)
        return Response({
            'message': f'Exam published successfully. Temporary OTPs are ready for {len(otps)} students.',
            'exam': ExamSerializer(exam).data,
            'otps_ready': len(otps),
        })

    def delete(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        exam.is_active = False
        exam.save(update_fields=['is_active'])
        return Response({
            'message': 'Exam unpublished successfully.',
            'exam': ExamSerializer(exam).data,
        })


class StartExamView(views.APIView):
    """
    Starts (or resumes) a secure exam session.
    Shuffles the MCQ order *and* the option order, per student, deterministically
    persisted so a refresh shows exactly the same paper.
    """
    permission_classes = [IsStudent]

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        student = request.user
        now = timezone.now()

        if not exam.is_active:
            return Response({'error': 'This exam has not been published by faculty yet.'},
                            status=status.HTTP_403_FORBIDDEN)
        allocation_ok, allocated, remaining, allocation_message = exam_mark_allocation_status(exam)
        if not allocation_ok:
            return Response({'error': f'This exam is not ready. {allocation_message}'},
                            status=status.HTTP_403_FORBIDDEN)
        if now < exam.start_time:
            return Response({'error': f'Exam has not started yet. It begins at {timezone.localtime(exam.start_time).strftime("%d %b %Y, %I:%M %p")}.'},
                            status=status.HTTP_403_FORBIDDEN)
        if now >= exam.end_time:
            return Response({'error': 'The exam window has closed.'}, status=status.HTTP_403_FORBIDDEN)

        access = None
        temp_otp_input = str(request.data.get('temp_otp', '')).strip() if request.data else ''
        if exam.requires_otp:
            if not temp_otp_input:
                return Response({'error': 'Temporary exam OTP is required. Please enter your 6-digit temporary OTP on the exam page before starting.'}, status=status.HTTP_403_FORBIDDEN)
            access = StudentExamAccess.objects.filter(exam=exam, student=student, temp_otp=temp_otp_input, is_active=True).first()
            if not access:
                return Response({'error': 'Invalid or expired temporary exam OTP for this exam. Please check with your faculty.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            access = StudentExamAccess.objects.filter(exam=exam, student=student, is_active=True).first()

        with transaction.atomic():
            # Nested atomic = savepoint: if two near-simultaneous requests (e.g. a
            # double-tapped "Start Exam" button) both race to create the session,
            # the loser's IntegrityError only rolls back the savepoint and we
            # simply re-fetch the winner's row instead of failing the request.
            existing = StudentExamSession.objects.filter(exam=exam, student=student).first()
            if existing is None:
                try:
                    with transaction.atomic():
                        session = StudentExamSession.objects.create(exam=exam, student=student)
                        created = True
                except IntegrityError:
                    session = StudentExamSession.objects.get(exam=exam, student=student)
                    created = False
            else:
                session, created = existing, False

            if session.status in ('submitted', 'evaluated'):
                return Response({'error': 'You have already submitted this exam.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if session.is_locked:
                return Response({'error': 'Your session was locked due to repeated proctoring violations. Contact your invigilator.'},
                                status=status.HTTP_403_FORBIDDEN)
            if timezone.now() >= session.deadline:
                return Response({'error': 'Your exam time has expired. The secure room is closed for this attempt.'},
                                status=status.HTTP_403_FORBIDDEN)

            if access and not access.used_at:
                access.used_at = now
                access.save(update_fields=['used_at'])

            all_mcqs = list(MCQQuestion.objects.filter(exam=exam))
            all_ids = [q.id for q in all_mcqs]

            order = [qid for qid in (session.shuffled_mcq_order or []) if qid in all_ids]
            new_ids = [qid for qid in all_ids if qid not in order]
            if new_ids:
                random.shuffle(new_ids)
                order.extend(new_ids)
            if created and not session.shuffled_mcq_order:
                random.shuffle(order)

            # Shuffle the A/B/C/D option order per question, per student.
            opts = dict(session.shuffled_options or {})
            for qid in order:
                key = str(qid)
                existing = opts.get(key)
                if not existing or sorted(existing) != ['A', 'B', 'C', 'D']:
                    perm = ['A', 'B', 'C', 'D']
                    random.shuffle(perm)
                    opts[key] = perm

            session.shuffled_mcq_order = order
            session.shuffled_options = opts
            session.save(update_fields=['shuffled_mcq_order', 'shuffled_options'])

        mcq_map = {q.id: q for q in all_mcqs}
        payload_mcqs = []
        for qid in order:
            q = mcq_map.get(qid)
            if not q:
                continue
            perm = opts[str(qid)]
            source = {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d}
            display = {}
            # display slot i shows the text of original option perm[i]
            for slot, origin in zip(['A', 'B', 'C', 'D'], perm):
                display[f'option_{slot.lower()}'] = source[origin]
            payload_mcqs.append({
                'id': q.id,
                'question_text': q.question_text,
                'question_type': q.question_type,
                'marks': q.marks,
                'negative_marks': q.negative_marks,
                **display,
            })

        coding_problems = CodingProblem.objects.filter(exam=exam).order_by('id')

        return Response({
            'session_id': session.id,
            'exam': ExamSerializer(exam).data,
            'mcqs': payload_mcqs,
            'coding_problems': CodingProblemStudentSerializer(coding_problems, many=True).data,
            'remaining_seconds': session.remaining_seconds(),
            'server_time': now,
            'mcq_draft': session.mcq_draft or {},
            'coding_draft': session.coding_draft or {},
            'violation_count': session.violation_count,
            'proctor_config': {
                'enforce_fullscreen': exam.enforce_fullscreen,
                'block_shortcuts': exam.block_shortcuts,
                'block_copy_paste': exam.block_copy_paste,
                'require_screen_recording': exam.require_screen_recording,
                'max_violations': exam.max_violations,
                'auto_submit_on_violation': exam.auto_submit_on_violation,
            },
        })


class ExamAutoSaveView(views.APIView):
    """Periodically persists the student's in-progress answers server-side."""
    permission_classes = [IsStudent]

    def post(self, request, exam_id):
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).first()
        if not session:
            return Response({'error': 'No active session.'}, status=status.HTTP_404_NOT_FOUND)
        if session.status != 'in_progress':
            return Response({'error': 'Session is not in progress.'}, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() >= session.deadline:
            return Response({'error': 'Exam time has expired. Autosave is closed.', 'remaining_seconds': 0},
                            status=status.HTTP_403_FORBIDDEN)

        mcq = request.data.get('mcq_answers')
        coding = request.data.get('coding_answers')
        if isinstance(mcq, dict):
            session.mcq_draft = mcq
        if isinstance(coding, dict):
            session.coding_draft = coding
        session.last_autosave_at = timezone.now()
        session.save(update_fields=['mcq_draft', 'coding_draft', 'last_autosave_at'])

        return Response({'saved_at': session.last_autosave_at,
                         'remaining_seconds': session.remaining_seconds()})


class ProctorEventView(views.APIView):
    """
    Records an anti-cheat violation. Returns the running violation count and
    tells the client whether the session must now be force-submitted.
    """
    permission_classes = [IsStudent]

    HIGH = {'fullscreen_exit', 'tab_switch', 'devtools'}
    MEDIUM = {'blur', 'paste', 'copy', 'cut'}

    def post(self, request, exam_id):
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).first()
        if not session:
            return Response({'error': 'No active session.'}, status=status.HTTP_404_NOT_FOUND)

        event_type = str(request.data.get('event_type', 'other'))[:30]
        # Backward compatibility: older clients sent focus_loss for window blur.
        if event_type == 'focus_loss':
            event_type = 'blur'
        valid = {c[0] for c in ProctorEvent.EVENT_CHOICES}
        if event_type not in valid:
            event_type = 'other'
        details = str(request.data.get('details', ''))[:500]

        severity = 'high' if event_type in self.HIGH else ('medium' if event_type in self.MEDIUM else 'low')
        counts_as_violation = severity in ('high', 'medium')

        ProctorEvent.objects.create(session=session, event_type=event_type,
                                    severity=severity, details=details)

        if counts_as_violation and session.status == 'in_progress':
            session.violation_count = (session.violation_count or 0) + 1
            session.save(update_fields=['violation_count'])

        exam = session.exam
        limit = exam.max_violations or 0
        must_void = bool(
            exam.auto_submit_on_violation and limit > 0
            and session.violation_count >= limit
            and session.status == 'in_progress'
        )

        if must_void:
            # Unfair means: void the session to zero (not a normal auto-submit
            # with whatever marks were earned) and lock the student's whole
            # account — they cannot sign back in to the portal at all until a
            # faculty member clears it from the exam roster.
            now = timezone.now()
            reason = f"Exceeded the {limit}-violation proctoring limit in \"{exam.title}\" ({event_type} at {session.violation_count} violations)."
            session.status = 'ufm'
            session.is_ufm = True
            session.is_locked = True
            session.is_auto_submitted = True
            session.ufm_reason = reason
            session.submitted_at = now
            session.mcq_score = 0.0
            session.coding_score = 0.0
            session.total_score = 0.0
            session.is_passed = False
            session.save(update_fields=[
                'status', 'is_ufm', 'is_locked', 'is_auto_submitted', 'ufm_reason',
                'submitted_at', 'mcq_score', 'coding_score', 'total_score', 'is_passed',
            ])
            # Zero out any marks already awarded on individual responses too, so
            # nothing in the per-question breakdown contradicts the 0 total.
            MCQResponse.objects.filter(session=session).update(marks_awarded=0.0, is_correct=False)
            CodingSubmission.objects.filter(session=session).update(marks_awarded=0.0, logic_status='incorrect')

            student = session.student
            student.is_blocked = True
            student.blocked_reason = reason
            student.blocked_at = now
            student.save(update_fields=['is_blocked', 'blocked_reason', 'blocked_at'])

            ProctorEvent.objects.create(session=session, event_type='auto_submit', severity='high',
                                        details=f"UFM — account locked. {reason}")

        return Response({
            'violation_count': session.violation_count,
            'max_violations': limit,
            'severity': severity,
            'counted': counts_as_violation,
            'must_auto_submit': must_void,
            'is_ufm': must_void,
            'blocked': must_void,
            'remaining_seconds': session.remaining_seconds(),
        })


class ProctorRecordingUploadView(views.APIView):
    """Upload a short screen-recording clip for a proctoring incident."""
    permission_classes = [IsStudent]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, exam_id):
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).first()
        if not session:
            return Response({'error': 'No active session.'}, status=status.HTTP_404_NOT_FOUND)

        clip = request.FILES.get('clip')
        if not clip:
            return Response({'error': 'Recording clip is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Reject empty/near-empty clips. Those usually show as 0:00 files and
        # are not useful proctoring evidence.
        if clip.size < 25 * 1024:
            return Response({'error': 'Recording clip is too short or empty.'}, status=status.HTTP_400_BAD_REQUEST)
        # Keep accidental uploads bounded. Focus-loss clips can cover the whole
        # away period, so allow larger WebM evidence files than the older short
        # edge-only clips.
        if clip.size > 100 * 1024 * 1024:
            return Response({'error': 'Recording clip is too large.'}, status=status.HTTP_400_BAD_REQUEST)
        import os
        ext = os.path.splitext((clip.name or '').lower())[1]
        content_type = (getattr(clip, 'content_type', '') or '').lower()
        allowed_ext = {'.webm', '.mp4', '.mov', '.m4v'}
        allowed_types = {'video/webm', 'video/mp4', 'video/quicktime', 'application/octet-stream'}
        if ext not in allowed_ext or (content_type and content_type not in allowed_types):
            return Response({'error': 'Recording clip must be a WebM/MP4 video file.'}, status=status.HTTP_400_BAD_REQUEST)

        event_type = str(request.data.get('event_type', 'other'))[:30]
        # New clients use the same canonical label as ProctorEvent; accept the
        # older focus_loss recording label for backward compatibility.
        if event_type == 'focus_loss':
            event_type = 'blur'
        if event_type not in ('blur', 'tab_switch'):
            return Response({'error': 'Recording clips are accepted only for blur/focus loss or tab switching.'},
                            status=status.HTTP_400_BAD_REQUEST)
        details = str(request.data.get('details', ''))[:500]
        rec = ProctorRecording.objects.create(
            session=session, event_type=event_type, details=details, clip=clip
        )
        return Response({
            'message': 'Screen recording clip uploaded.',
            'recording': ProctorRecordingSerializer(rec, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


class RunCodeView(views.APIView):
    """
    "Run Code" during an exam: executes the student's current code against
    either the problem's sample input or custom stdin they supply, and
    returns stdout/stderr. This never touches marks by itself — grading only
    happens at submission time via the AI-first evaluator.
    """
    permission_classes = [IsStudent]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'code_run'

    def post(self, request, exam_id, problem_id):
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).first()
        if not session:
            return Response({'error': 'Start the exam before running code.'}, status=status.HTTP_404_NOT_FOUND)
        if session.status != 'in_progress':
            return Response({'error': 'This exam session is no longer in progress.'}, status=status.HTTP_400_BAD_REQUEST)
        if timezone.now() >= session.deadline:
            return Response({'error': 'Exam time has expired. Code execution is closed.'}, status=status.HTTP_403_FORBIDDEN)

        problem = CodingProblem.objects.filter(id=problem_id, exam_id=exam_id).first()
        if not problem:
            return Response({'error': 'Coding problem not found.'}, status=status.HTTP_404_NOT_FOUND)

        code = str(request.data.get('code', '') or '')
        if not code.strip():
            return Response({'error': 'Nothing to run — write some code first.'}, status=status.HTTP_400_BAD_REQUEST)

        stdin_text = request.data.get('stdin')
        if stdin_text is None or str(stdin_text).strip() == '':
            stdin_text = problem.sample_input or ''

        # The compiler/interpreter is fixed to the problem's language — a
        # student cannot run their answer as any language but the one the
        # question was set in.
        result = run_code(code, problem.language, str(stdin_text))
        result['language'] = problem.language
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class SubmitExamView(views.APIView):
    permission_classes = [IsStudent]

    def post(self, request, exam_id):
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).first()
        if not session:
            return Response({'error': 'No exam session found. Please start the exam first.'},
                            status=status.HTTP_404_NOT_FOUND)

        if session.status in ('submitted', 'evaluated', 'ufm'):
            return Response({'error': 'Exam already submitted.'}, status=status.HTTP_400_BAD_REQUEST)

        exam = session.exam
        deadline_expired = timezone.now() >= session.deadline
        if deadline_expired:
            # After the deadline, never trust fresh client answers: the student
            # may have kept the page open or manipulated the client timer. Grade
            # only the last server-side autosaved draft captured before expiry.
            mcq_answers = dict(session.mcq_draft or {})
            coding_answers = dict(session.coding_draft or {})
            auto = True
            reason = 'Time expired. Graded using the last server autosave before the deadline.'
        else:
            mcq_answers = request.data.get('mcq_answers') or {}
            coding_answers = request.data.get('coding_answers') or {}
            auto = bool(request.data.get('auto_submitted', False))
            reason = str(request.data.get('reason', ''))[:200]

            if not isinstance(mcq_answers, dict):
                mcq_answers = {}
            if not isinstance(coding_answers, dict):
                coding_answers = {}

            # Fall back to the server-side draft for anything the client omitted
            for k, v in (session.mcq_draft or {}).items():
                mcq_answers.setdefault(str(k), v)
            for k, v in (session.coding_draft or {}).items():
                coding_answers.setdefault(str(k), v)

        with transaction.atomic():
            # ---------------- MCQ evaluation ----------------
            questions = {q.id: q for q in MCQQuestion.objects.filter(exam_id=exam_id)}
            opts = session.shuffled_options or {}
            total_mcq_marks = 0.0

            for qid, question in questions.items():
                perm = opts.get(str(qid))

                def _to_actual(slot):
                    """Translate a displayed A/B/C/D slot back to the real option letter."""
                    if not slot:
                        return None
                    slot = str(slot).strip().upper()
                    if slot not in ('A', 'B', 'C', 'D'):
                        return None
                    if perm and len(perm) == 4:
                        return perm[['A', 'B', 'C', 'D'].index(slot)]
                    return slot

                if question.question_type == 'multi':
                    raw = mcq_answers.get(str(qid), mcq_answers.get(qid))
                    raw_list = raw if isinstance(raw, list) else ([raw] if raw else [])
                    actual_options = sorted({o for o in (_to_actual(s) for s in raw_list) if o})

                    if not actual_options:
                        is_correct, marks = False, 0.0  # unattempted -> no negative
                    elif set(actual_options) == question.correct_set():
                        is_correct, marks = True, float(question.marks)
                    else:
                        is_correct, marks = False, -float(question.negative_marks or 0.0)

                    total_mcq_marks += marks
                    MCQResponse.objects.update_or_create(
                        session=session, question=question,
                        defaults={
                            'selected_option': None,
                            'selected_options': actual_options,
                            'is_correct': is_correct,
                            'marks_awarded': round(marks, 2),
                        },
                    )
                    continue

                raw = mcq_answers.get(str(qid), mcq_answers.get(qid))
                actual_option = _to_actual(raw)

                if actual_option is None:
                    is_correct, marks = False, 0.0          # unattempted -> no negative
                elif actual_option == question.correct_option.upper():
                    is_correct, marks = True, float(question.marks)
                else:
                    is_correct, marks = False, -float(question.negative_marks or 0.0)

                total_mcq_marks += marks

                MCQResponse.objects.update_or_create(
                    session=session, question=question,
                    defaults={
                        'selected_option': actual_option,
                        'selected_options': [],
                        'is_correct': is_correct,
                        'marks_awarded': round(marks, 2),
                    },
                )

            total_mcq_marks = max(0.0, total_mcq_marks)   # never below zero overall

            # ---------------- Coding evaluation ----------------
            total_coding_marks = 0.0
            has_background_coding = False
            problems = CodingProblem.objects.filter(exam_id=exam_id)

            for problem in problems:
                sub_data = coding_answers.get(str(problem.id), coding_answers.get(problem.id)) or {}
                if not isinstance(sub_data, dict):
                    sub_data = {'code': str(sub_data)}
                code = flatten_coding_answer(sub_data).strip()
                # The compiler is fixed to the problem's language — whatever the
                # client sends for `language` is ignored, never trusted as a switch.
                lang = problem.language

                # Calling an external AI model here made the submit button wait
                # once per coding question. Save non-empty answers as pending and
                # evaluate them after the transaction commits instead.
                if code:
                    has_background_coding = True
                    verdict = {
                        'logic_status': 'pending', 'marks_awarded': 0.0,
                        'feedback': 'Coding evaluation is in progress. Faculty review remains available.',
                        'matched_reference': '', 'test_passed_count': 0, 'test_total_count': 0,
                        'hidden_failed_count': 0, 'failed_visible_tests': [], 'ai_debug': {},
                    }
                    evaluated_by = 'pending'
                else:
                    verdict, evaluated_by = gemini_evaluate_coding_submission(code, lang, problem, [])
                total_coding_marks += verdict['marks_awarded']

                CodingSubmission.objects.update_or_create(
                    session=session, problem=problem,
                    defaults={
                        'language': lang,
                        'submitted_code': code,
                        'logic_status': verdict['logic_status'],
                        'marks_awarded': verdict['marks_awarded'],
                        'faculty_feedback': verdict['feedback'],
                        'matched_reference': verdict['matched_reference'] or '',
                        'evaluated_by': evaluated_by,
                        'marks_overridden': False,
                        'test_passed_count': int(verdict.get('test_passed_count', 0) or 0),
                        'test_total_count': int(verdict.get('test_total_count', 0) or 0),
                        'hidden_failed_count': int(verdict.get('hidden_failed_count', 0) or 0),
                        'failed_visible_tests': verdict.get('failed_visible_tests', []) or [],
                        'ai_detected_approach': (verdict.get('ai_debug') or {}).get('detected_approach', '')[:255],
                        'ai_logic_summary': (verdict.get('ai_debug') or {}).get('logic_summary', ''),
                        'ai_mistake_explanation': (verdict.get('ai_debug') or {}).get('mistake_explanation', ''),
                        'ai_corrected_code': (verdict.get('ai_debug') or {}).get('corrected_code', ''),
                        'ai_predicted_output': (verdict.get('ai_debug') or {}).get('predicted_output', ''),
                        'ai_debug_source': (verdict.get('ai_debug') or {}).get('source', ''),
                    },
                )

            session.status = 'submitted' if has_background_coding else 'evaluated'
            session.submitted_at = timezone.now()
            session.mcq_score = round(total_mcq_marks, 2)
            session.coding_score = round(total_coding_marks, 2)
            session.total_score = round(session.mcq_score + session.coding_score, 2)
            session.is_passed = session.total_score >= exam.passing_marks
            session.is_auto_submitted = auto
            session.faculty_verified = False
            session.faculty_verified_at = None
            session.faculty_verified_by = None
            session.mcq_draft = {}
            session.coding_draft = {}
            session.save()

            if auto:
                ProctorEvent.objects.create(
                    session=session, event_type='auto_submit', severity='high',
                    details=reason or 'Auto-submitted by the system.',
                )

            # Clear the temporary OTP - it must not survive the exam.
            StudentExamAccess.objects.filter(exam_id=exam_id, student=request.user).update(
                is_active=False, cleared_at=timezone.now()
            )

        if has_background_coding:
            transaction.on_commit(lambda: threading.Thread(
                target=evaluate_coding_submissions_in_background, args=(session.id,), daemon=True
            ).start())

        if request.user.email:
            threading.Thread(
                target=send_submission_receipt,
                args=(request.user.email, exam.title, session.submitted_at), daemon=True,
            ).start()
        notify(request.user, 'exam', f'Submission received: {exam.title}',
               'Your submission was saved successfully. Results will appear after faculty publication.', f'/exam/{exam_id}/result')
        audit(request, 'exam_submitted', session, {'auto_submitted': auto})
        return Response({
            'message': ('Exam submitted. Coding evaluation is running in the background.' if has_background_coding
                        else 'Exam submitted and evaluated successfully.') + ' Your temporary OTP has been cleared.',
            'auto_submitted': auto,
            # reveal_override: this is a receipt of the student's own submit
            # action (never rendered by the frontend, which just navigates
            # away), not a "view my results" surface — so it isn't subject
            # to the exam.results_released gate applied everywhere else.
            'session': StudentExamSessionSerializer(
                session, context={'request': request, 'reveal_override': True}
            ).data,
        })


class StudentExamResultView(views.APIView):
    """A student's own result. Always scoped to request.user - a student can
    never read another candidate's session, even by guessing an exam id.

    Marks, verdicts and pass/fail are hidden (via StudentExamSessionSerializer)
    until Exam.results_released — i.e. until faculty publishes results after verification has
    closed for every candidate, not just this one. That keeps an early
    finisher from learning their score (and relaying it to classmates still
    sitting the exam) before everyone is done."""
    permission_classes = [IsAuthenticated]

    def get(self, request, exam_id):
        try:
            session = StudentExamSession.objects.get(exam_id=exam_id, student=request.user)
        except StudentExamSession.DoesNotExist:
            return Response({'error': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StudentExamSessionSerializer(session, context={'request': request})
        return Response(serializer.data)


class EvaluateCodingSubmissionView(views.APIView):
    """
    Faculty can override coding submission grade / logic status
    """
    permission_classes = [IsFaculty]

    def post(self, request, submission_id):
        try:
            sub = CodingSubmission.objects.get(id=submission_id)
        except CodingSubmission.DoesNotExist:
            return Response({'error': 'Submission not found'}, status=status.HTTP_404_NOT_FOUND)

        logic_status = str(request.data.get('logic_status', sub.logic_status))
        valid = {c[0] for c in CodingSubmission.LOGIC_STATUS_CHOICES}
        if logic_status not in valid:
            return Response({'error': f"logic_status must be one of {sorted(valid)}"},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            marks_awarded = float(request.data.get('marks_awarded', sub.marks_awarded))
        except (TypeError, ValueError):
            return Response({'error': 'marks_awarded must be a number.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Clamp within the problem's allowed range
        marks_awarded = max(0.0, min(marks_awarded, float(sub.problem.marks)))
        feedback = request.data.get('faculty_feedback', sub.faculty_feedback)

        sub.logic_status = logic_status
        sub.marks_awarded = round(marks_awarded, 2)
        sub.faculty_feedback = feedback
        sub.reviewed_by_faculty = True
        sub.save()

        # Recalculate session total
        session = sub.session
        total_coding = sum(s.marks_awarded for s in session.coding_submissions.all())
        session.coding_score = round(total_coding, 2)
        session.total_score = round(session.mcq_score + session.coding_score, 2)
        session.is_passed = (session.total_score >= session.exam.passing_marks)
        update_fields = ['coding_score', 'total_score', 'is_passed']
        # Re-grading one coding answer should not verify the whole attempt unless
        # every coding submission in that session has now been manually reviewed.
        all_coding_reviewed = not session.coding_submissions.filter(reviewed_by_faculty=False).exists()
        if all_coding_reviewed:
            session.faculty_verified = True
            session.faculty_verified_at = timezone.now()
            session.faculty_verified_by = request.user
            update_fields += ['faculty_verified', 'faculty_verified_at', 'faculty_verified_by']
        session.save(update_fields=update_fields)

        return Response({
            'message': 'Submission re-evaluated successfully.',
            'submission': CodingSubmissionSerializer(sub, context={'request': request}).data,
            'session_total': session.total_score,
        })


class LeaderboardView(views.APIView):
    """
    Ranked results.

    PRIVACY: students must not see other students' marks. A student receives
    only their own full row; every other row is anonymised to a rank plus a
    masked label, with all score fields stripped. Faculty see everything.

    TIMING: for students, the whole leaderboard (including cohort stats) is
    withheld until Exam.results_released — ranks and averages would leak
    information about the exam to anyone still sitting it. Faculty are
    never gated by this.
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _mask(enrollment):
        """EN2026001 -> EN••••001 so a student can still recognise density, not identity."""
        if not enrollment:
            return 'Candidate'
        e = str(enrollment)
        if len(e) <= 5:
            return e[:2] + '•' * (len(e) - 2)
        return f"{e[:2]}{'•' * (len(e) - 5)}{e[-3:]}"

    def get(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        if not faculty_can_view_exam(request.user, exam):
            return Response({'error': 'This assessment is not available.'}, status=status.HTTP_403_FORBIDDEN)

        is_faculty = request.user.user_type == 'faculty'
        released = is_faculty or exam.results_released

        if not released:
            # Nobody but faculty gets ranks, marks or cohort stats (average,
            # highest, etc.) before the exam window closes — those numbers
            # would themselves leak information to students still sitting
            # the exam.
            total_participants = StudentExamSession.objects.filter(
                exam_id=exam_id, status='evaluated'
            ).count()
            return Response({
                'leaderboard': [],
                'total_participants': total_participants,
                'my_rank': None,
                'is_masked_view': True,
                'results_released': False,
                'exam_end_time': exam.end_time,
            })

        sessions = (StudentExamSession.objects
                    .filter(exam_id=exam_id, status='evaluated')
                    .select_related('student', 'exam')
                    .order_by('-total_score', 'submitted_at'))

        rows = []
        prev_score = None
        prev_rank = 0
        for idx, session in enumerate(sessions, start=1):
            # Standard competition ranking: equal scores share a rank.
            if prev_score is not None and session.total_score == prev_score:
                rank = prev_rank
            else:
                rank = idx
                prev_rank = idx
                prev_score = session.total_score
            rows.append((rank, session))

        total_marks = exam.total_marks or 0
        data = []
        for rank, session in rows:
            is_you = session.student_id == request.user.id

            if is_faculty or is_you:
                data.append({
                    'rank': rank,
                    'session_id': session.id,
                    'student_name': session.student.name,
                    'enrollment_no': session.student.enrollment_no,
                    'department': session.student.department,
                    'mcq_score': session.mcq_score,
                    'coding_score': session.coding_score,
                    'total_score': session.total_score,
                    'percentage': round((session.total_score / total_marks * 100), 2) if total_marks else 0,
                    'is_passed': session.is_passed,
                    'is_you': is_you,
                    'is_masked': False,
                    'submitted_at': session.submitted_at,
                })
            else:
                # Anonymised row: rank only, no marks, no name.
                data.append({
                    'rank': rank,
                    'session_id': None,
                    'student_name': self._mask(session.student.enrollment_no),
                    'enrollment_no': None,
                    'department': session.student.department,
                    'mcq_score': None,
                    'coding_score': None,
                    'total_score': None,
                    'percentage': None,
                    'is_passed': None,
                    'is_you': False,
                    'is_masked': True,
                    'submitted_at': None,
                })

        me = next((r for r in data if r['is_you']), None)

        payload = {
            'leaderboard': data,
            'total_participants': len(data),
            'my_rank': me['rank'] if me else None,
            'is_masked_view': not is_faculty,
            'results_released': True,
            'exam_end_time': exam.end_time,
        }

        # Give the student cohort context without exposing anyone's marks.
        if not is_faculty and rows:
            scores = [s.total_score for _, s in rows]
            payload['cohort'] = {
                'highest_score': round(max(scores), 2),
                'average_score': round(sum(scores) / len(scores), 2),
                'total_marks': total_marks,
            }
            if me:
                better = sum(1 for sc in scores if sc < (me['total_score'] or 0))
                payload['cohort']['percentile'] = round((better / len(scores)) * 100, 1)

        return Response(payload)


class ResultsView(views.APIView):
    """
    Cross-exam results dashboard powering the "All Results" tab (renamed
    from "Leaderboard"). Faculty see every student's attempt across every
    exam, filterable and exportable to CSV. Students only ever get their
    own rows (the same privacy rule as the per-exam leaderboard) — for them
    this is "My Result": every exam they've taken, filterable the same way.

    A student's own scores in this list are hidden until each exam's
    results_released flips True (see Exam.results_released); faculty rows
    are never gated.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_faculty = user.user_type == 'faculty'

        sessions = (StudentExamSession.objects
                    .filter(status__in=['submitted', 'evaluated', 'ufm'])
                    .select_related('student', 'exam'))
        if not is_faculty:
            sessions = sessions.filter(student=user)

        # ---- filters ----
        q = request.query_params
        min_score = q.get('min_score')
        max_score = q.get('max_score')
        phase = (q.get('phase') or '').strip().upper()
        subject = (q.get('subject') or '').strip()
        search = (q.get('search') or '').strip().lower()

        # min_score/max_score are applied in Python below, after masking —
        # filtering at the DB level would leak a hidden score through
        # whether the row survives the filter, even with the number itself
        # blanked out in the response.
        if phase:
            sessions = sessions.filter(exam__phase=phase)
        if subject:
            sessions = sessions.filter(exam__subject__iexact=subject)
        if search:
            if is_faculty:
                sessions = sessions.filter(
                    Q(student__name__icontains=search) | Q(student__enrollment_no__icontains=search)
                )
            else:
                sessions = sessions.filter(exam__title__icontains=search)

        sessions = sessions.order_by('-submitted_at').select_related('exam', 'student')

        rows = []
        for s in sessions:
            total_marks = s.exam.total_marks or 0
            # Students can't see their own marks for a session until that
            # exam's window has closed for everyone; faculty always can.
            released = is_faculty or s.exam.results_released
            rows.append({
                'session_id': s.id,
                'exam_id': s.exam_id,
                'exam_title': s.exam.title,
                'subject': s.exam.subject,
                'phase': s.exam.phase,
                'student_id': s.student_id,
                'student_name': s.student.name,
                'enrollment_no': s.student.enrollment_no,
                'department': s.student.department,
                'mcq_score': s.mcq_score if released else None,
                'coding_score': s.coding_score if released else None,
                'total_score': s.total_score if released else None,
                'total_marks': total_marks,
                'percentage': (round((s.total_score / total_marks) * 100, 2) if total_marks else 0) if released else None,
                'is_passed': s.is_passed if released else None,
                'status': s.status,
                'is_ufm': s.is_ufm,
                'submitted_at': s.submitted_at,
                'results_released': released,
                'exam_end_time': s.exam.end_time,
            })

        if min_score not in (None, ''):
            try:
                v = float(min_score)
                rows = [r for r in rows if not r['results_released'] or (r['total_score'] is not None and r['total_score'] >= v)]
            except ValueError:
                pass
        if max_score not in (None, ''):
            try:
                v = float(max_score)
                rows = [r for r in rows if not r['results_released'] or (r['total_score'] is not None and r['total_score'] <= v)]
            except ValueError:
                pass

        if q.get('export') == 'csv':
            return self._csv_response(rows, is_faculty)

        subjects = list(Exam.objects.exclude(subject='').values_list('subject', flat=True).distinct())
        page_rows, page_meta = paginate_rows(request, rows)
        return Response({'results': page_rows, 'available_subjects': subjects, **page_meta})

    def _csv_response(self, rows, is_faculty):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        filename = 'results.csv' if is_faculty else 'my_result.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        header = ['Exam', 'Subject', 'Phase', 'MCQ Score', 'Coding Score', 'Total Score',
                  'Total Marks', 'Percentage', 'Result', 'Status', 'Submitted At']
        if is_faculty:
            header = ['Student Name', 'Enrollment No', 'Department'] + header
        writer.writerow(header)
        for r in rows:
            if r['is_ufm']:
                result_label = 'Unfair Means'
            elif not r['results_released']:
                # is_passed is None here — 'Fail' would be wrong (None is
                # falsy), and it hasn't actually failed, it's just not
                # released yet.
                result_label = 'Pending'
            else:
                result_label = 'Pass' if r['is_passed'] else 'Fail'
            row = [r['exam_title'], r['subject'], r['phase'], r['mcq_score'], r['coding_score'],
                   r['total_score'], r['total_marks'], r['percentage'],
                   result_label,
                   'Unfair Means' if r['is_ufm'] else r['status'].title(),
                   r['submitted_at']]
            if is_faculty:
                row = [r['student_name'], r['enrollment_no'], r['department']] + row
            writer.writerow(row)
        return response


class ExamRosterView(views.APIView):
    """
    Per-exam roster for faculty: who has been granted access, who has joined
    (started a session) but not finished, who has submitted, and who hasn't
    started at all. Also backs the filterable student list on the Analytics
    page (#12) via the same shape.
    """
    permission_classes = [IsFaculty]

    def get(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        access_map = {a.student_id: a for a in StudentExamAccess.objects.filter(exam=exam).select_related('student')}
        session_map = {s.student_id: s for s in StudentExamSession.objects.filter(exam=exam).select_related('student')}

        student_ids = set(access_map) | set(session_map)
        total_marks = exam.total_marks or 0
        rows = []
        for sid in student_ids:
            access = access_map.get(sid)
            session = session_map.get(sid)
            student = (session.student if session else access.student)

            if session is None:
                roster_status = 'not_started'
            elif session.status == 'in_progress':
                roster_status = 'in_progress'
            elif session.status == 'ufm':
                roster_status = 'ufm'
            else:
                roster_status = 'submitted'

            rows.append({
                'student_id': sid,
                'name': student.name,
                'enrollment_no': student.enrollment_no,
                'department': student.department,
                'access_granted': access is not None,
                'otp_active': bool(access and access.is_active),
                'is_blocked': student.is_blocked,
                'status': roster_status,
                'joined_at': session.started_at if session else None,
                'submitted_at': session.submitted_at if session else None,
                'faculty_verified': bool(session.faculty_verified) if session else False,
                'faculty_verified_at': session.faculty_verified_at if session else None,
                'violation_count': session.violation_count if session else 0,
                'session_status': session.status if session else None,
                'total_score': session.total_score if session else None,
                'percentage': round((session.total_score / total_marks) * 100, 2) if (session and total_marks) else None,
                'is_passed': session.is_passed if session else None,
            })

        rows.sort(key=lambda r: (r['status'] != 'ufm', r['status'] == 'not_started', r['name'] or ''))
        counts = {
            'not_started': sum(1 for r in rows if r['status'] == 'not_started'),
            'in_progress': sum(1 for r in rows if r['status'] == 'in_progress'),
            'submitted': sum(1 for r in rows if r['status'] == 'submitted'),
            'ufm': sum(1 for r in rows if r['status'] == 'ufm'),
        }
        result_status = result_publication_status(exam)
        page_rows, page_meta = paginate_rows(request, rows)
        can_manage = faculty_can_review_exam(request.user, exam)
        return Response({'roster': page_rows, 'counts': counts, 'result_status': result_status,
                          'can_manage': can_manage, **page_meta})


class StudentExamAnalysisView(views.APIView):
    """Full breakdown of one student's attempt at one exam, for faculty review (#5)."""
    permission_classes = [IsFaculty]

    def get(self, request, exam_id, student_id):
        session = (StudentExamSession.objects
                   .filter(exam_id=exam_id, student_id=student_id)
                   .select_related('student', 'exam').first())
        if not session:
            student = User.objects.filter(id=student_id, user_type='student').first()
            if not student:
                return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response({'error': f'{student.name} has not started this exam yet.', 'not_started': True},
                            status=status.HTTP_404_NOT_FOUND)
        events = ProctorEvent.objects.filter(session=session).order_by('created_at')
        recordings = ProctorRecording.objects.filter(session=session).order_by('created_at')
        data = StudentExamSessionSerializer(session, context={'request': request}).data
        data['proctor_events'] = ProctorEventSerializer(events, many=True).data
        data['proctor_recordings'] = ProctorRecordingSerializer(recordings, many=True, context={'request': request}).data
        data['result_status'] = result_publication_status(session.exam)
        data['can_manage'] = faculty_can_review_exam(request.user, session.exam)
        return Response(data)


class UpdateStudentMarksView(views.APIView):
    """
    Faculty manually overrides marks for individual MCQ responses and/or
    coding submissions within one student's session, then the session totals
    are recomputed from the (possibly overridden) individual marks (#6).
    """
    permission_classes = [IsFaculty]

    def patch(self, request, exam_id, student_id):
        session = (StudentExamSession.objects
                   .filter(exam_id=exam_id, student_id=student_id)
                   .select_related('exam').first())
        if not session:
            return Response({'error': 'This student has no session for this exam.'}, status=status.HTTP_404_NOT_FOUND)
        if not faculty_can_review_exam(request.user, session.exam):
            return Response({'error': 'Only faculty from this branch can change marks.'}, status=status.HTTP_403_FORBIDDEN)
        if session.status == 'ufm':
            return Response({'error': 'This session was voided for unfair means and cannot be re-marked.'},
                            status=status.HTTP_400_BAD_REQUEST)

        mcq_overrides = request.data.get('mcq_overrides') or {}
        coding_overrides = request.data.get('coding_overrides') or {}

        with transaction.atomic():
            for response_id, marks in mcq_overrides.items():
                try:
                    marks = float(marks)
                except (TypeError, ValueError):
                    continue
                resp = MCQResponse.objects.filter(id=response_id, session=session).select_related('question').first()
                if not resp:
                    continue
                q = resp.question
                lo, hi = (-float(q.negative_marks or 0), float(q.marks))
                marks = max(lo, min(hi, marks))
                resp.marks_awarded = marks
                resp.marks_overridden = True
                resp.save(update_fields=['marks_awarded', 'marks_overridden'])
            for submission_id, marks in coding_overrides.items():
                try:
                    marks = float(marks)
                except (TypeError, ValueError):
                    continue
                sub = CodingSubmission.objects.filter(id=submission_id, session=session).first()
                if not sub:
                    continue
                max_marks = sub.problem.marks
                marks = max(0.0, min(float(max_marks), marks))
                sub.marks_awarded = marks
                sub.marks_overridden = True
                sub.reviewed_by_faculty = True
                sub.save(update_fields=['marks_awarded', 'marks_overridden', 'reviewed_by_faculty'])

            session.refresh_from_db()
            mcq_total = MCQResponse.objects.filter(session=session).aggregate(t=Sum('marks_awarded'))['t'] or 0
            coding_total = CodingSubmission.objects.filter(session=session).aggregate(t=Sum('marks_awarded'))['t'] or 0
            session.mcq_score = round(mcq_total, 2)
            session.coding_score = round(coding_total, 2)
            session.total_score = round(mcq_total + coding_total, 2)
            session.is_passed = session.total_score >= (session.exam.passing_marks or 0)
            session.faculty_verified = True
            session.faculty_verified_at = timezone.now()
            session.faculty_verified_by = request.user
            session.save(update_fields=[
                'mcq_score', 'coding_score', 'total_score', 'is_passed',
                'faculty_verified', 'faculty_verified_at', 'faculty_verified_by'
            ])

        audit(request, 'marks_overridden', session, {
            'mcq_response_count': len(mcq_overrides),
            'coding_submission_count': len(coding_overrides),
        })
        return Response(StudentExamSessionSerializer(session, context={'request': request}).data)


class VerifyStudentSessionView(views.APIView):
    """Faculty marks a student's evaluated/voided attempt as reviewed."""
    permission_classes = [IsFaculty]

    def post(self, request, exam_id, student_id):
        session = (StudentExamSession.objects
                   .filter(exam_id=exam_id, student_id=student_id)
                   .select_related('exam', 'student').first())
        if not session:
            return Response({'error': 'This student has no session for this exam.'}, status=status.HTTP_404_NOT_FOUND)
        if not faculty_can_review_exam(request.user, session.exam):
            return Response({'error': 'Only faculty from this branch can verify this student.'}, status=status.HTTP_403_FORBIDDEN)
        if session.status == 'submitted':
            return Response({'error': 'Coding evaluation is still in progress. Please verify once it is complete.'}, status=status.HTTP_400_BAD_REQUEST)
        if session.status not in ('evaluated', 'ufm'):
            return Response({'error': 'Only evaluated or voided sessions can be verified.'}, status=status.HTTP_400_BAD_REQUEST)
        mark_session_verified(session, request.user)
        return Response(StudentExamSessionSerializer(session, context={'request': request}).data)


class PublishResultsView(views.APIView):
    """Release student-visible results only after faculty verification."""
    permission_classes = [IsFaculty]

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        if timezone.now() < exam.end_time:
            return Response({'error': 'Results cannot be published before the exam window closes.'}, status=status.HTTP_400_BAD_REQUEST)
        status_info = result_publication_status(exam)
        if status_info['total_attempted'] <= 0:
            return Response({'error': 'No student attempts exist for this exam yet.'}, status=status.HTTP_400_BAD_REQUEST)
        if status_info['in_progress'] > 0:
            return Response({'error': f"{status_info['in_progress']} session(s) are still in progress."}, status=status.HTTP_400_BAD_REQUEST)
        if status_info['unverified'] > 0:
            return Response({'error': f"Verify all student attempts before publishing. Remaining unverified: {status_info['unverified']}."}, status=status.HTTP_400_BAD_REQUEST)
        exam.results_published = True
        exam.results_published_at = timezone.now()
        exam.save(update_fields=['results_published', 'results_published_at'])
        audit(request, 'results_published', exam)
        for student_id in StudentExamSession.objects.filter(exam=exam).values_list('student_id', flat=True).distinct():
            notify(User.objects.get(id=student_id), 'result', f'Results published: {exam.title}', 'Your verified result is now available.', f'/exam/{exam.id}/result')
        return Response({
            'message': 'Results published successfully. Students can now view marks, verdicts and solutions.',
            'exam': ExamSerializer(exam).data,
            'result_status': result_publication_status(exam),
        })

    def delete(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        exam.results_published = False
        exam.results_published_at = None
        exam.save(update_fields=['results_published', 'results_published_at'])
        return Response({'message': 'Results unpublished successfully.', 'exam': ExamSerializer(exam).data})



class AnalyticsView(views.APIView):
    """
    Aggregate performance analytics with chart-ready series.

    PRIVACY: aggregates are safe for everyone, but per-question accuracy and
    score distributions are only meaningful in aggregate — no individual
    student marks are ever returned here. Students additionally receive their
    own scores so the charts can show a "you are here" marker.

    TIMING: for students this entire endpoint is withheld until
    Exam.results_released — even the class-wide numbers would tip off
    someone still sitting the exam. Faculty are never gated by this; they
    can watch analytics update live while the exam is in progress.
    """
    permission_classes = [IsAuthenticated]

    BANDS = [
        ('0-20%',   0,  20),
        ('21-40%',  20, 40),
        ('41-60%',  40, 60),
        ('61-80%',  60, 80),
        ('81-100%', 80, 100.01),
    ]

    def _absolute_chart_urls(self, request, exam_id, charts):
        """Charts are regenerated fresh on every request, but their filenames are
        stable per exam — without a cache-buster the browser would keep showing
        a stale image after new submissions are evaluated. Also matches the rest
        of the API (attachment_url, clip_url) by returning absolute URLs."""
        bust = int(timezone.now().timestamp())
        out = {}
        for k, v in charts.items():
            if not v:
                out[k] = None
                continue
            filename = str(v).rsplit('/', 1)[-1]
            abs_url = request.build_absolute_uri(f'/api/exams/{exam_id}/analytics/chart/{filename}/')
            sep = '&' if '?' in abs_url else '?'
            out[k] = f'{abs_url}{sep}v={bust}'
        return out

    def get(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        is_faculty = request.user.user_type == 'faculty'
        released = is_faculty or exam.results_released

        if not released:
            # Faculty can watch analytics update live as an exam runs — that's
            # useful monitoring. Students cannot: even the aggregate numbers
            # (class average, pass rate, which question is hardest) would leak
            # information about the exam to someone still sitting it.
            return Response({
                'exam_title': exam.title,
                'total_marks': exam.total_marks or 0,
                'passing_marks': exam.passing_marks,
                'results_released': False,
                'exam_end_time': exam.end_time,
            })

        total_registered = StudentExamAccess.objects.filter(exam=exam).count()
        sessions = (StudentExamSession.objects
                    .filter(exam=exam, status='evaluated')
                    .select_related('student'))
        total_appeared = sessions.count()
        total_marks = exam.total_marks or 0

        # Charts are only generated once below, for whichever branch actually
        # gets returned — regenerating a throwaway "empty" set on every request
        # (even when there's real data to show) wasted a full matplotlib render.
        problem_stats_empty = [{'id': p.id, 'title': (p.title[:40] + '…') if len(p.title) > 40 else p.title, 'submissions': 0, 'correct': 0, 'partial': 0, 'incorrect': 0, 'avg_marks': 0, 'max_marks': p.marks} for p in CodingProblem.objects.filter(exam=exam)]

        if total_appeared == 0:
            charts_empty = generate_analytics_charts(exam_id, {
                'score_distribution': [{'band': b[0], 'count': 0} for b in self.BANDS],
                'passed_count': 0,
                'failed_count': 0,
                'section_comparison': [],
                'coding_status_breakdown': [],
                'question_stats': [],
                'problem_stats': problem_stats_empty,
            })
            return Response({
                'exam_title': exam.title,
                'total_marks': total_marks,
                'passing_marks': exam.passing_marks,
                'total_registered': total_registered,
                'total_appeared': 0,
                'passed_count': 0,
                'failed_count': 0,
                'highest_score': 0,
                'lowest_score': 0,
                'avg_score': 0,
                'avg_mcq': 0,
                'avg_coding': 0,
                'median_score': 0,
                'question_stats': [],
                'score_distribution': [{'band': b[0], 'count': 0} for b in self.BANDS],
                'section_comparison': [],
                'coding_status_breakdown': [],
                'problem_stats': problem_stats_empty,
                'my_scores': None,
                'chart_images': self._absolute_chart_urls(request, exam_id, charts_empty),
                'results_released': True,
            })

        stats = sessions.aggregate(
            highest=Max('total_score'), lowest=Min('total_score'),
            avg=Avg('total_score'), avg_mcq=Avg('mcq_score'), avg_coding=Avg('coding_score'),
        )
        passed_count = sessions.filter(is_passed=True).count()

        scores = sorted(s.total_score for s in sessions)
        mid = len(scores) // 2
        median = scores[mid] if len(scores) % 2 else (scores[mid - 1] + scores[mid]) / 2

        # ---- Score distribution histogram ----
        distribution = []
        for label, lo, hi in self.BANDS:
            count = 0
            for sc in scores:
                pct = (sc / total_marks * 100) if total_marks else 0
                if lo < pct <= hi or (lo == 0 and pct == 0):
                    count += 1
            distribution.append({'band': label, 'count': count})

        # ---- Per-question accuracy ----
        mcqs = MCQQuestion.objects.filter(exam=exam)
        question_stats = []
        for i, q in enumerate(mcqs, start=1):
            responses = MCQResponse.objects.filter(question=q, session__in=sessions)
            total_resp = responses.count()
            correct_resp = responses.filter(is_correct=True).count()
            if q.question_type == 'multi':
                attempted = sum(1 for r in responses if isinstance(r.selected_options, list) and len(r.selected_options) > 0)
            else:
                attempted = responses.exclude(selected_option__isnull=True).count()
            # Accuracy must be calculated from attempts, not every response
            # record. A response row can exist for a question a student left
            # blank, and counting it as wrong made hard-question analytics
            # misleading and inflated the incorrect total.
            accuracy = round((correct_resp / attempted * 100), 1) if attempted else 0.0
            question_stats.append({
                'id': q.id,
                'label': f'Q{i}',
                'question_text': (q.question_text[:70] + '…') if len(q.question_text) > 70 else q.question_text,
                'correct_option': q.correct_option if is_faculty else None,
                'total_responses': total_resp,
                'attempted': attempted,
                'correct_responses': correct_resp,
                'incorrect_responses': max(0, attempted - correct_resp),
                'accuracy_percent': accuracy,
            })

        # ---- Section comparison (MCQ vs Coding, as % of section total) ----
        mcq_total = sum(q.marks for q in mcqs) or 0
        coding_total = sum(p.marks for p in CodingProblem.objects.filter(exam=exam)) or 0
        section_comparison = [
            {
                'section': 'MCQ',
                'average': round(stats['avg_mcq'] or 0, 2),
                'max_possible': round(mcq_total, 2),
                'average_percent': round(((stats['avg_mcq'] or 0) / mcq_total * 100), 1) if mcq_total else 0,
            },
            {
                'section': 'Coding',
                'average': round(stats['avg_coding'] or 0, 2),
                'max_possible': round(coding_total, 2),
                'average_percent': round(((stats['avg_coding'] or 0) / coding_total * 100), 1) if coding_total else 0,
            },
        ]

        # ---- Coding logic verdict breakdown ----
        verdict_counts = {'correct': 0, 'partial': 0, 'incorrect': 0, 'pending': 0}
        for sub in CodingSubmission.objects.filter(session__in=sessions):
            verdict_counts[sub.logic_status] = verdict_counts.get(sub.logic_status, 0) + 1
        coding_status_breakdown = [
            {'status': k, 'count': v} for k, v in verdict_counts.items() if v > 0
        ]

        # ---- Per-problem coding performance ----
        problem_stats = []
        for p in CodingProblem.objects.filter(exam=exam):
            subs = CodingSubmission.objects.filter(problem=p, session__in=sessions)
            n = subs.count()
            problem_stats.append({
                'id': p.id,
                'title': (p.title[:40] + '…') if len(p.title) > 40 else p.title,
                'submissions': n,
                'correct': subs.filter(logic_status='correct').count(),
                'partial': subs.filter(logic_status='partial').count(),
                'incorrect': subs.filter(logic_status='incorrect').count(),
                'avg_marks': round(subs.aggregate(a=Avg('marks_awarded'))['a'] or 0, 2),
                'max_marks': p.marks,
            })

        # ---- The requesting student's own scores (never anyone else's) ----
        my_scores = None
        if not is_faculty:
            mine = sessions.filter(student=request.user).first()
            if mine:
                my_scores = {
                    'mcq_score': mine.mcq_score,
                    'coding_score': mine.coding_score,
                    'total_score': mine.total_score,
                    'percentage': round((mine.total_score / total_marks * 100), 2) if total_marks else 0,
                    'is_passed': mine.is_passed,
                }

        # Generate Python-based charts using matplotlib/seaborn (always, so URLs exist)
        charts = generate_analytics_charts(exam_id, {
            'score_distribution': distribution if total_appeared > 0 else [{'band': b[0], 'count': 0} for b in self.BANDS],
            'passed_count': passed_count,
            'failed_count': total_appeared - passed_count,
            'section_comparison': section_comparison,
            'coding_status_breakdown': coding_status_breakdown,
            'question_stats': question_stats,
            'problem_stats': problem_stats,
        })

        return Response({
            'exam_title': exam.title,
            'total_marks': total_marks,
            'passing_marks': exam.passing_marks,
            'total_registered': total_registered,
            'total_appeared': total_appeared,
            'passed_count': passed_count,
            'failed_count': total_appeared - passed_count,
            'highest_score': round(stats['highest'] or 0, 2),
            'lowest_score': round(stats['lowest'] or 0, 2),
            'avg_score': round(stats['avg'] or 0, 2),
            'avg_mcq': round(stats['avg_mcq'] or 0, 2),
            'avg_coding': round(stats['avg_coding'] or 0, 2),
            'median_score': round(median, 2),
            'question_stats': question_stats,
            'score_distribution': distribution,
            'section_comparison': section_comparison,
            'coding_status_breakdown': coding_status_breakdown,
            'problem_stats': problem_stats,
            'my_scores': my_scores,
            'chart_images': self._absolute_chart_urls(request, exam_id, charts),
            'results_released': True,
        })


class AnalyticsChartImageView(views.APIView):
    """Authenticated chart image endpoint.

    The generated PNG files still live under MEDIA_ROOT/analytics internally,
    but clients receive API URLs so charts are protected by the same faculty /
    published-results permissions as the JSON analytics endpoint.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, exam_id, filename):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        is_faculty = request.user.user_type == 'faculty'
        has_access = is_faculty or StudentExamAccess.objects.filter(exam=exam, student=request.user).exists()
        if not has_access:
            return Response({'error': 'You do not have access to this exam.'}, status=status.HTTP_403_FORBIDDEN)
        if not is_faculty and not exam.results_released:
            return Response({'error': 'Analytics charts are available after results are published.'}, status=status.HTTP_403_FORBIDDEN)

        safe_name = str(filename or '').split('/')[-1]
        expected_prefix = f'{exam_id}_'
        if not safe_name.startswith(expected_prefix) or not safe_name.endswith('.png'):
            return Response({'error': 'Chart not found.'}, status=status.HTTP_404_NOT_FOUND)
        path = settings.MEDIA_ROOT / 'analytics' / safe_name
        if not path.exists() or not path.is_file():
            return Response({'error': 'Chart not found.'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(open(path, 'rb'), content_type='image/png')


class StudentSubmissionsListView(views.APIView):
    permission_classes = [IsFaculty]

    def get(self, request, exam_id):
        sessions = StudentExamSession.objects.filter(exam_id=exam_id).select_related('student').order_by('-started_at')
        return Response(StudentExamSessionSerializer(sessions, many=True, context={'request': request}).data)


# ============================================================
#  NOTES MODULE VIEWS
# ============================================================

class FacultyNoteViewSet(viewsets.ModelViewSet):
    """
    Faculty: full CRUD over study notes (supports file upload).
    Students: read-only, filtered by visibility rules.
    """
    serializer_class = FacultyNoteSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsFaculty()]

    def get_queryset(self):
        user = self.request.user
        qs = FacultyNote.objects.select_related('uploaded_by', 'exam')

        if user.user_type == 'faculty':
            if self.request.query_params.get('mine') == 'true':
                qs = qs.filter(uploaded_by=user)
        else:
            dept = (user.department or '').strip()
            exam_ids = StudentExamAccess.objects.filter(student=user).values_list('exam_id', flat=True)
            qs = qs.filter(is_published=True).filter(
                Q(visibility='all')
                | Q(visibility='department', department__iexact=dept)
                | Q(visibility='exam', exam_id__in=list(exam_ids))
            )

        subject = self.request.query_params.get('subject')
        if subject:
            qs = qs.filter(subject__iexact=subject)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(subject__icontains=search)
                | Q(description__icontains=search)
                | Q(content__icontains=search)
            )
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    def perform_update(self, serializer):
        note = self.get_object()
        if note.uploaded_by_id != self.request.user.id:
            raise PermissionDenied("You can only edit notes that you uploaded.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.uploaded_by_id != self.request.user.id:
            raise PermissionDenied("You can only delete notes that you uploaded.")
        instance.delete()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class StudentNoteViewSet(viewsets.ModelViewSet):
    """A student's own private notebook. Strictly scoped to request.user."""
    serializer_class = StudentNoteSerializer
    permission_classes = [IsStudent]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = StudentNote.objects.filter(student=self.request.user)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(content__icontains=search)
                | Q(tags__icontains=search)
                | Q(subject__icontains=search)
            )
        subject = self.request.query_params.get('subject')
        if subject:
            qs = qs.filter(subject__iexact=subject)
        return qs

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class NotesSubjectsView(views.APIView):
    """Distinct subject list, used to populate filter dropdowns."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        faculty_subjects = (FacultyNote.objects.exclude(subject='')
                            .values_list('subject', flat=True).distinct())
        my_subjects = []
        if request.user.user_type == 'student':
            my_subjects = (StudentNote.objects.filter(student=request.user)
                           .exclude(subject='').values_list('subject', flat=True).distinct())
        return Response({
            'faculty_subjects': sorted(set(faculty_subjects)),
            'my_subjects': sorted(set(my_subjects)),
        })


# ============================================================
#  REFERENCE SOLUTION MANAGEMENT
# ============================================================

class ReferenceSolutionView(views.APIView):
    """Add / update / remove reference solutions on an existing coding problem."""
    permission_classes = [IsFaculty]

    def post(self, request, problem_id):
        problem = CodingProblem.objects.filter(id=problem_id).select_related('exam').first()
        if not problem:
            return Response({'error': 'Coding problem not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(problem.exam)
        if locked:
            return locked

        title = str(request.data.get('title', '')).strip()
        code = str(request.data.get('code', '')).strip()
        if not title or not code:
            return Response({'error': 'Both title and code are required for a reference solution.'},
                            status=status.HTTP_400_BAD_REQUEST)

        sol = ReferenceSolution.objects.create(
            problem=problem,
            title=title,
            language=problem.language,
            code=code,
            logic_explanation=str(request.data.get('logic_explanation', '')),
        )
        return Response(ReferenceSolutionSerializer(sol).data, status=status.HTTP_201_CREATED)

    def patch(self, request, problem_id, solution_id):
        sol = ReferenceSolution.objects.filter(id=solution_id, problem_id=problem_id).select_related('problem__exam').first()
        if not sol:
            return Response({'error': 'Reference solution not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(sol.problem.exam)
        if locked:
            return locked
        data = dict(request.data)
        data.pop('language', None)  # a solution's language always follows its problem's fixed language
        serializer = ReferenceSolutionSerializer(sol, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, problem_id, solution_id):
        sol = ReferenceSolution.objects.filter(id=solution_id, problem_id=problem_id).select_related('problem__exam').first()
        if not sol:
            return Response({'error': 'Reference solution not found'}, status=status.HTTP_404_NOT_FOUND)
        locked = content_locked_response(sol.problem.exam)
        if locked:
            return locked
        sol.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
#  STUDENT EXAM LIST  (fixes "no active exam" dead-end)
# ============================================================

class MyExamsView(views.APIView):
    """
    Every exam the logged-in student has access to, with live status
    and their session state. Powers the student dashboard.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        now = timezone.now()
        accesses = (StudentExamAccess.objects
                    .filter(student=request.user, exam__is_active=True)
                    .select_related('exam')
                    .order_by('-exam__start_time'))

        sessions = {s.exam_id: s for s in
                    StudentExamSession.objects.filter(student=request.user)}

        items = []
        for acc in accesses:
            exam = acc.exam
            session = sessions.get(exam.id)
            allocation_ok, _, _, _ = exam_mark_allocation_status(exam)
            if not allocation_ok and not (session and session.status in ('submitted', 'evaluated')):
                continue
            if now < exam.start_time:
                state = 'upcoming'
            elif now >= exam.end_time:
                state = 'closed'
            else:
                state = 'live'
            if session and session.status in ('submitted', 'evaluated', 'ufm'):
                state = 'completed'

            # Marks stay hidden from the dashboard card until the exam window
            # has closed for every candidate — the UFM flag is still shown
            # immediately since that's conduct/status, not a mark, and the
            # student already learned about it in real time during the exam.
            released = exam.results_released
            reveal_score = bool(session) and released

            items.append({
                'exam': ExamSerializer(exam).data,
                'state': state,
                'otp_active': acc.is_active,
                'session_status': session.status if session else None,
                'total_score': session.total_score if reveal_score else None,
                'is_passed': session.is_passed if reveal_score else None,
                'is_ufm': bool(session.is_ufm) if session else False,
                'results_released': released,
                'remaining_seconds': session.remaining_seconds() if (session and session.status == 'in_progress') else None,
            })

        return Response({'exams': items, 'server_time': now})


class ProctorReportView(views.APIView):
    """Admin-only view of all proctoring violations for an exam."""
    permission_classes = [IsAdmin]

    def get(self, request, exam_id):
        sessions = (StudentExamSession.objects
                    .filter(exam_id=exam_id)
                    .select_related('student')
                    .prefetch_related('proctor_events')
                    .order_by('-violation_count'))

        report = []
        for s in sessions:
            events = list(s.proctor_events.all())
            recordings = [
                r for r in s.screen_recordings.filter(event_type__in=['blur', 'focus_loss', 'tab_switch'])
                if r.clip and getattr(r.clip, 'size', 0) >= 25 * 1024
            ]
            report.append({
                'session_id': s.id,
                'student_name': s.student.name,
                'enrollment_no': s.student.enrollment_no,
                'status': s.status,
                'violation_count': s.violation_count,
                'is_auto_submitted': s.is_auto_submitted,
                'is_locked': s.is_locked,
                'is_ufm': s.is_ufm,
                'student_id': s.student_id,
                'student_blocked': s.student.is_blocked,
                'events': ProctorEventSerializer(events, many=True).data,
                'recordings': ProctorRecordingSerializer(recordings, many=True, context={'request': request}).data,
            })
        return Response({'report': report})


# ============================================================
#  UNFAIR-MEANS ACCOUNT LOCKS
# ============================================================

class BlockedStudentsView(views.APIView):
    """Admin-only list of every student account currently locked for unfair means."""
    permission_classes = [IsAdmin]

    def get(self, request):
        blocked = User.objects.filter(user_type='student', is_blocked=True).order_by('-blocked_at')
        data = []
        for s in blocked:
            last_ufm = (StudentExamSession.objects.filter(student=s, is_ufm=True)
                        .select_related('exam').order_by('-submitted_at').first())
            data.append({
                'id': s.id,
                'name': s.name,
                'enrollment_no': s.enrollment_no,
                'blocked_reason': s.blocked_reason,
                'blocked_at': s.blocked_at,
                'exam_id': last_ufm.exam_id if last_ufm else None,
                'exam_title': last_ufm.exam.title if last_ufm else None,
            })
        return Response(data)


class UnblockStudentView(views.APIView):
    """Admin restores portal access for a student locked out by the UFM system."""
    permission_classes = [IsAdmin]

    def post(self, request, student_id):
        student = User.objects.filter(id=student_id, user_type='student').first()
        if not student:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        student.is_blocked = False
        student.blocked_reason = ''
        student.blocked_at = None
        student.save(update_fields=['is_blocked', 'blocked_reason', 'blocked_at'])
        audit(request, 'student_unblocked', student)
        return Response({
            'message': f'{student.name} can sign in to the portal again.',
            'user': UserSerializer(student).data,
        })


class PasswordResetRequestView(views.APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        identifier = str(request.data.get('identifier', '')).strip()
        # Deliberately use a generic response to prevent account enumeration.
        message = 'If an account matches those details, reset instructions have been sent.'
        if not identifier:
            return Response({'message': message})
        user = (User.objects.filter(username__iexact=identifier).first()
                or User.objects.filter(email__iexact=identifier).first()
                or User.objects.filter(enrollment_no__iexact=identifier).first())
        if not user or not user.email:
            return Response({'message': message})
        PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        reset = PasswordResetToken.objects.create(user=user, expires_at=timezone.now() + timedelta(minutes=30))
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset.token}"
        send_mail('Reset your Academia Pro password',
                  f'Use this link within 30 minutes to reset your password: {reset_url}',
                  None, [user.email], fail_silently=True)
        return Response({'message': message})


class PasswordResetConfirmView(views.APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        token = str(request.data.get('token', '')).strip()
        password = str(request.data.get('password', ''))
        record = PasswordResetToken.objects.select_related('user').filter(token=token).first()
        if not record or not record.is_valid:
            return Response({'error': 'This reset link is invalid or has expired.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password, record.user)
        except ValidationError as error:
            return Response({'error': list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
        record.user.set_password(password)
        record.user.save(update_fields=['password'])
        record.used_at = timezone.now()
        record.save(update_fields=['used_at'])
        return Response({'message': 'Password reset successfully. You can now sign in.'})


class NotificationView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        limit = min(max(int(request.query_params.get('limit', 30)), 1), 100)
        return Response({
            'notifications': [{
                'id': n.id, 'type': n.notification_type, 'title': n.title, 'body': n.body,
                'link': n.link, 'is_read': n.is_read, 'created_at': n.created_at,
            } for n in notifications[:limit]],
            'unread_count': notifications.filter(is_read=False).count(),
        })

    def patch(self, request):
        ids = request.data.get('ids') or []
        qs = Notification.objects.filter(recipient=request.user, is_read=False)
        if ids:
            qs = qs.filter(id__in=ids)
        qs.update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditLogView(views.APIView):
    """Admin-only, paginated visibility into sensitive operations."""
    permission_classes = [IsAdmin]

    def get(self, request):
        logs = AuditLog.objects.select_related('actor').exclude(action__in=['faculty_login', 'student_login', 'password_reset_requested', 'password_reset_completed'])
        action = request.query_params.get('action', '').strip()
        if action:
            logs = logs.filter(action=action)
        rows = [{
            'id': log.id, 'action': log.action, 'actor': log.actor.name if log.actor else 'System',
            'target_type': log.target_type, 'target_id': log.target_id, 'details': log.details,
            'ip_address': log.ip_address, 'created_at': log.created_at,
        } for log in logs[:1000]]
        page_rows, page_meta = paginate_rows(request, rows)
        return Response({'logs': page_rows, **page_meta})


class AdminOverviewView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        recent_logs = AuditLog.objects.select_related('actor').exclude(action__in=['faculty_login', 'student_login', 'password_reset_requested', 'password_reset_completed'])[:10]
        return Response({
            'counts': {
                'students': User.objects.filter(user_type='student').count(),
                'faculty': User.objects.filter(user_type='faculty').count(),
                'admins': User.objects.filter(Q(user_type='admin') | Q(is_staff=True) | Q(is_superuser=True)).distinct().count(),
                'exams': Exam.objects.count(),
                'blocked_students': User.objects.filter(user_type='student', is_blocked=True).count(),
                'open_appeals': ExamAppeal.objects.filter(status__in=['open', 'reviewing']).count(),
                'proctor_events': ProctorEvent.objects.count(),
            },
            'recent_audit': [{'id': log.id, 'action': log.action, 'actor': log.actor.name if log.actor else 'System', 'target_type': log.target_type, 'created_at': log.created_at} for log in recent_logs],
            'blocked_students': [UserSerializer(u).data for u in User.objects.filter(user_type='student', is_blocked=True)[:20]],
        })


class AdminUsersView(views.APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        role = request.query_params.get('role')
        users = User.objects.all().order_by('user_type', 'name', 'username')
        if role in ('student', 'faculty', 'admin'):
            users = users.filter(Q(user_type='admin') | Q(is_staff=True) | Q(is_superuser=True)) if role == 'admin' else users.filter(user_type=role)
        return Response({'users': UserSerializer(users[:300], many=True).data})

    def post(self, request):
        role = request.data.get('user_type')
        if role not in ('student', 'faculty', 'admin'):
            return Response({'error': 'user_type must be student, faculty, or admin.'}, status=status.HTTP_400_BAD_REQUEST)
        username = str(request.data.get('username') or '').strip()
        password = str(request.data.get('password') or '').strip()
        if not username or not password:
            return Response({'error': 'username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username__iexact=username).exists():
            return Response({'error': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        branch = str(request.data.get('branch') or '').strip().upper() if role in ('student', 'faculty') else ''
        valid_branches = {value for value, _ in User.BRANCH_CHOICES}
        if role in ('student', 'faculty') and branch not in valid_branches:
            return Response({'error': 'Student and faculty accounts require a valid branch.'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.create_user(username=username, password=password, user_type=role, name=str(request.data.get('name') or username), email=str(request.data.get('email') or ''), department='', branch=branch, enrollment_no=(str(request.data.get('enrollment_no') or '').strip() or None), faculty_subjects=str(request.data.get('faculty_subjects') or '').strip() if role == 'faculty' else '', must_change_password=True)
        if role == 'admin':
            user.is_staff = True; user.save(update_fields=['is_staff'])
        audit(request, 'admin_user_created', user, {'role': role})
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(views.APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        role = request.data.get('user_type', user.user_type)
        if role not in ('student', 'faculty', 'admin'):
            return Response({'error': 'Invalid user type.'}, status=status.HTTP_400_BAD_REQUEST)
        branch = str(request.data.get('branch', user.branch) or '').strip().upper()
        if role in ('student', 'faculty') and branch not in {value for value, _ in User.BRANCH_CHOICES}:
            return Response({'error': 'Student and faculty accounts require a valid branch.'}, status=status.HTTP_400_BAD_REQUEST)
        for field in ('username', 'name', 'email', 'enrollment_no'):
            if field in request.data:
                value = str(request.data[field] or '').strip()
                if field == 'enrollment_no':
                    value = value or None
                setattr(user, field, value)
        user.user_type = role
        user.branch = branch if role in ('student', 'faculty') else ''
        user.department = ''
        user.faculty_subjects = str(request.data.get('faculty_subjects', user.faculty_subjects) or '').strip() if role == 'faculty' else ''
        user.is_staff = role == 'admin'
        try:
            user.save()
        except IntegrityError:
            return Response({'error': 'Username or enrollment number already exists.'}, status=status.HTTP_400_BAD_REQUEST)
        audit(request, 'admin_user_updated', user, {'role': role, 'branch': user.branch})
        return Response(UserSerializer(user).data)

    def delete(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response(status=status.HTTP_204_NO_CONTENT)
        if user.id == request.user.id:
            return Response({'error': 'You cannot delete your own account.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.is_superuser:
            return Response({'error': 'A superuser account cannot be deleted here.'}, status=status.HTTP_400_BAD_REQUEST)
        audit(request, 'admin_user_deleted', user, {'username': user.username})
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserPasswordResetView(views.APIView):
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        temp_password = get_random_string(10)
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password'])
        audit(request, 'admin_password_reset', user)
        return Response({'message': 'Temporary password generated.', 'username': user.username, 'temp_password': temp_password})


class StudentTrendView(views.APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        sessions = (StudentExamSession.objects.filter(student=request.user, exam__results_published=True,
                    status__in=['submitted', 'evaluated', 'ufm']).select_related('exam').order_by('submitted_at'))
        return Response({'trend': [{
            'exam_id': s.exam_id, 'exam_title': s.exam.title, 'subject': s.exam.subject,
            'completed_at': s.submitted_at, 'score': s.total_score,
            'total_marks': s.exam.total_marks, 'percentage': round(s.total_score / s.exam.total_marks * 100, 2) if s.exam.total_marks else 0,
        } for s in sessions]})


class PracticeQuestionsView(views.APIView):
    """Serves a random, ungraded MCQ set for the self-serve mock test.

    Deliberately stateless: no StudentExamSession, no proctoring, no OTP,
    no camera/microphone. A student can retake it as many times as they
    like; nothing here is ever visible to faculty.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        topic = request.query_params.get('topic', '').strip()
        try:
            count = min(20, max(5, int(request.query_params.get('count', 10))))
        except (TypeError, ValueError):
            count = 10
        pool = PracticeQuestion.objects.filter(is_active=True)
        if topic:
            pool = pool.filter(topic__iexact=topic)
        ids = list(pool.values_list('id', flat=True))
        random.shuffle(ids)
        picked = PracticeQuestion.objects.filter(id__in=ids[:count])
        by_id = {q.id: q for q in picked}
        ordered = [by_id[i] for i in ids[:count] if i in by_id]
        topics = list(PracticeQuestion.objects.filter(is_active=True).values_list('topic', flat=True).distinct().order_by('topic'))
        return Response({
            'topics': topics,
            'questions': [{
                'id': q.id, 'topic': q.topic, 'difficulty': q.difficulty, 'question_text': q.question_text,
                'options': {'A': q.option_a, 'B': q.option_b, 'C': q.option_c, 'D': q.option_d},
            } for q in ordered],
        })


class PracticeSubmitView(views.APIView):
    """Instantly grades a mock-test attempt. Nothing is persisted — the
    whole point of practice mode is a zero-stakes, zero-record retry loop."""
    permission_classes = [IsStudent]

    def post(self, request):
        answers = request.data.get('answers') or {}
        if not isinstance(answers, dict) or not answers:
            return Response({'error': 'No answers were submitted.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            question_ids = [int(qid) for qid in answers.keys()]
        except (TypeError, ValueError):
            return Response({'error': 'Malformed answer payload.'}, status=status.HTTP_400_BAD_REQUEST)
        questions = {q.id: q for q in PracticeQuestion.objects.filter(id__in=question_ids)}
        results, correct_count = [], 0
        for qid in question_ids:
            question = questions.get(qid)
            if not question:
                continue
            picked = str(answers.get(str(qid)) or '').upper()
            is_correct = picked == question.correct_option
            correct_count += int(is_correct)
            results.append({
                'id': qid, 'your_answer': picked or None, 'correct_answer': question.correct_option,
                'is_correct': is_correct, 'explanation': question.explanation,
            })
        total = len(results)
        return Response({
            'score': correct_count, 'total': total,
            'percentage': round(correct_count / total * 100, 1) if total else 0,
            'results': results,
        })


class QuestionQualityView(views.APIView):
    """Faculty psychometric summary; no student-level response data is exposed."""
    permission_classes = [IsFaculty]

    def get(self, request, exam_id):
        sessions = list(StudentExamSession.objects.filter(exam_id=exam_id, status__in=['submitted', 'evaluated']).order_by('total_score'))
        if not sessions:
            return Response({'questions': [], 'sample_size': 0})
        group_size = max(1, len(sessions) // 4)
        low_ids = {s.id for s in sessions[:group_size]}
        high_ids = {s.id for s in sessions[-group_size:]}
        rows = []
        for question in MCQQuestion.objects.filter(exam_id=exam_id):
            responses = MCQResponse.objects.filter(question=question, session__in=sessions)
            attempted = responses.count()
            correct = responses.filter(is_correct=True).count()
            high = responses.filter(session_id__in=high_ids, is_correct=True).count() / group_size
            low = responses.filter(session_id__in=low_ids, is_correct=True).count() / group_size
            rows.append({'id': question.id, 'label': question.question_text[:80], 'attempted': attempted,
                         'difficulty_percent': round(correct / attempted * 100, 1) if attempted else 0,
                         'discrimination': round(high - low, 3)})
        return Response({'questions': rows, 'sample_size': len(sessions), 'group_size': group_size})


class ResultPdfView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, exam_id):
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).select_related('exam', 'student').first()
        if not session or not session.exam.results_released:
            return Response({'error': 'A released result is required to download this card.'}, status=status.HTTP_404_NOT_FOUND)
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib import pyplot as plt
        stream = io.BytesIO()
        with PdfPages(stream) as pdf:
            figure = plt.figure(figsize=(8.27, 11.69)); figure.patch.set_facecolor('#fffef9'); figure.text(.1, .9, 'Academia Pro — Result Card', fontsize=22, weight='bold', color='#17201e');
            figure.text(.1, .81, f'Student: {session.student.name}\nEnrollment: {session.student.enrollment_no}\nExam: {session.exam.title}', fontsize=13, color='#53625e', linespacing=1.8)
            figure.text(.1, .62, f'Score\n{session.total_score:g} / {session.exam.total_marks:g}', fontsize=24, weight='bold', color='#5471d8')
            figure.text(.1, .48, f'MCQ: {session.mcq_score:g}\nCoding: {session.coding_score:g}\nResult: {"Pass" if session.is_passed else "Fail"}', fontsize=14, color='#17201e', linespacing=1.8); figure.text(.1, .12, 'Generated by Academia Pro. This document reflects released results only.', fontsize=9, color='#71817a'); pdf.savefig(figure, bbox_inches='tight'); plt.close(figure)
        stream.seek(0)
        return FileResponse(stream, as_attachment=True, filename=f'result-{exam_id}.pdf', content_type='application/pdf')


class ExamCalendarView(views.APIView):
    """Generates a downloadable .ics calendar invite for an exam window, so
    a student can add it to Google/Outlook/Apple Calendar, or a faculty
    member can add their own copy of the schedule."""
    permission_classes = [IsAuthenticated]

    def get(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        if not exam:
            return Response({'error': 'Assessment not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_owner_faculty = request.user.user_type == 'faculty' and exam.created_by_id == request.user.id
        has_student_access = StudentExamAccess.objects.filter(exam=exam, student=request.user).exists()
        if not (is_owner_faculty or has_student_access):
            return Response({'error': 'You do not have access to this assessment.'}, status=status.HTTP_403_FORBIDDEN)

        def ics_escape(text):
            return str(text or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')

        def ics_dt(dt):
            return timezone.localtime(dt, dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')

        description = (
            f'{exam.description}\\n\\n' if exam.description else ''
        ) + f'Duration once started: {exam.duration_minutes} minutes.'
        uid = f'exam-{exam.id}-{request.user.id}@academiapro'
        lines = [
            'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Academia Pro//Exam Schedule//EN',
            'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{ics_dt(timezone.now())}',
            f'DTSTART:{ics_dt(exam.start_time)}',
            f'DTEND:{ics_dt(exam.end_time)}',
            f'SUMMARY:{ics_escape(exam.title)}',
            f'DESCRIPTION:{ics_escape(description)}',
            'BEGIN:VALARM', 'TRIGGER:-PT30M', 'ACTION:DISPLAY', 'DESCRIPTION:Exam window opens soon', 'END:VALARM',
            'END:VEVENT', 'END:VCALENDAR',
        ]
        ics_content = '\r\n'.join(lines) + '\r\n'
        response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
        safe_title = re.sub(r'[^A-Za-z0-9]+', '-', exam.title).strip('-')[:60] or 'exam'
        response['Content-Disposition'] = f'attachment; filename="{safe_title}.ics"'
        return response


class QuestionBankPdfImportView(views.APIView):
    permission_classes = [IsFaculty]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'PDF file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not str(upload.name).lower().endswith('.pdf'):
            return Response({'error': 'Upload a .pdf file.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from pypdf import PdfReader
            reader = PdfReader(upload)
            text = '\n'.join(page.extract_text() or '' for page in reader.pages[:30])
        except Exception as exc:
            return Response({'error': f'Could not read PDF: {type(exc).__name__}'}, status=status.HTTP_400_BAD_REQUEST)
        items = self._items_from_text(text)
        created = []
        with transaction.atomic():
            for item in items[:100]:
                obj = QuestionBankItem.objects.create(owner=request.user, **item)
                created.append(QuestionBankView._serialize(obj))
        if created:
            audit(request, 'question_bank_pdf_imported', request.user, {'count': len(created), 'filename': upload.name})
        return Response({'created': len(created), 'items': created})

    @staticmethod
    def _items_from_text(text):
        lines = [re.sub(r'\s+', ' ', ln).strip() for ln in str(text or '').splitlines()]
        lines = [ln for ln in lines if ln]
        items, block = [], []
        def flush(block):
            joined = '\n'.join(block).strip()
            if not joined: return
            ans = re.search(r'(?:answer|correct)\s*[:\-]\s*([A-D])', joined, re.I)
            opts = {}
            for key in 'ABCD':
                m = re.search(rf'(?:^|\n)\s*{key}[\).:-]\s*(.*?)(?=\n\s*[A-D][\).:-]|\n\s*(?:answer|correct)\b|$)', joined, re.I | re.S)
                if m: opts[key] = ' '.join(m.group(1).split())
            if len(opts) == 4 and ans:
                qtext = re.split(r'\n\s*A[\).:-]', joined, maxsplit=1, flags=re.I)[0]
                qtext = re.sub(r'^\s*\d+[\).:-]\s*', '', qtext).strip()
                items.append({'kind': 'mcq', 'title': qtext[:200], 'subject': '', 'tags': 'pdf-import', 'payload': {'question_text': qtext, 'option_a': opts['A'], 'option_b': opts['B'], 'option_c': opts['C'], 'option_d': opts['D'], 'correct_option': ans.group(1).upper()}})
            elif re.search(r'\b(code|coding|program|algorithm|function)\b', joined, re.I):
                title = re.sub(r'^\s*\d+[\).:-]\s*', '', block[0]).strip()[:200]
                items.append({'kind': 'coding', 'title': title or 'Coding problem', 'subject': '', 'tags': 'pdf-import', 'payload': {'title': title or 'Coding problem', 'problem_statement': joined}})
        for ln in lines:
            if re.match(r'^\d+[\).]\s+', ln) and block:
                flush(block); block=[]
            block.append(ln)
        flush(block)
        return items


class QuestionBankView(views.APIView):
    permission_classes = [IsFaculty]

    def get(self, request):
        items = QuestionBankItem.objects.filter(owner=request.user)
        kind = request.query_params.get('kind')
        search = request.query_params.get('search', '').strip()
        if kind in ('mcq', 'coding'):
            items = items.filter(kind=kind)
        if search:
            items = items.filter(Q(title__icontains=search) | Q(subject__icontains=search) | Q(tags__icontains=search))
        return Response({'items': [self._serialize(item) for item in items]})

    def post(self, request):
        kind = request.data.get('kind')
        payload = request.data.get('payload') or {}
        if kind not in ('mcq', 'coding') or not isinstance(payload, dict):
            return Response({'error': 'A valid kind and payload are required.'}, status=status.HTTP_400_BAD_REQUEST)
        item = QuestionBankItem.objects.create(
            owner=request.user, kind=kind, payload=payload,
            title=str(request.data.get('title') or payload.get('title') or payload.get('question_text') or '')[:200],
            subject=str(request.data.get('subject', ''))[:120], tags=str(request.data.get('tags', ''))[:255],
        )
        audit(request, 'question_bank_created', item)
        return Response(self._serialize(item), status=status.HTTP_201_CREATED)

    def delete(self, request, item_id):
        item = QuestionBankItem.objects.filter(id=item_id, owner=request.user).first()
        if not item:
            return Response({'error': 'Question-bank item not found.'}, status=status.HTTP_404_NOT_FOUND)
        audit(request, 'question_bank_deleted', item)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _serialize(item):
        return {'id': item.id, 'kind': item.kind, 'title': item.title, 'subject': item.subject,
                'tags': item.tags, 'payload': item.payload, 'created_at': item.created_at, 'updated_at': item.updated_at}


class CloneExamView(views.APIView):
    permission_classes = [IsFaculty]

    def post(self, request, exam_id):
        source = Exam.objects.filter(id=exam_id).first()
        if not source:
            return Response({'error': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        if not start_time or not end_time:
            return Response({'error': 'A new start_time and end_time are required.'}, status=status.HTTP_400_BAD_REQUEST)
        from django.utils.dateparse import parse_datetime
        start, end = parse_datetime(str(start_time)), parse_datetime(str(end_time))
        if not start or not end or end <= start:
            return Response({'error': 'Provide a valid exam window.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            clone = Exam.objects.create(
                title=str(request.data.get('title') or f'{source.title} (copy)')[:200],
                description=source.description, subject=source.subject, phase=source.phase,
                created_by=request.user, start_time=start, end_time=end,
                duration_minutes=source.duration_minutes, passing_marks=source.passing_marks,
                total_marks=source.total_marks, is_active=False, content_locked=False,
                results_published=False, requires_otp=source.requires_otp,
                enforce_fullscreen=source.enforce_fullscreen, block_shortcuts=source.block_shortcuts,
                block_copy_paste=source.block_copy_paste, require_screen_recording=source.require_screen_recording,
                max_violations=source.max_violations, auto_submit_on_violation=source.auto_submit_on_violation,
            )
            for question in source.mcq_questions.all():
                question.pk = None
                question.exam = clone
                question.save()
            for old_problem in source.coding_problems.all():
                test_cases = list(old_problem.test_cases.all())
                solutions = list(old_problem.reference_solutions.all())
                old_problem.pk = None
                old_problem.exam = clone
                old_problem.save()
                for case in test_cases:
                    case.pk = None
                    case.problem = old_problem
                    case.save()
                for solution in solutions:
                    solution.pk = None
                    solution.problem = old_problem
                    solution.save()
            auto_generate_exam_otps(clone, reset_existing=True)
        audit(request, 'exam_cloned', clone, {'source_exam_id': source.id})
        return Response({'message': 'Exam cloned as a draft.', 'exam': ExamSerializer(clone).data}, status=status.HTTP_201_CREATED)


class BulkRosterImportView(views.APIView):
    permission_classes = [IsFaculty]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, exam_id):
        exam = Exam.objects.filter(id=exam_id).first()
        upload = request.FILES.get('file')
        if not exam:
            return Response({'error': 'Exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not upload:
            return Response({'error': 'Upload a CSV file.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = csv.DictReader(io.TextIOWrapper(upload.file, encoding='utf-8-sig'))
            created = updated = 0
            errors = []
            temp_credentials = []
            for line, row in enumerate(rows, start=2):
                enrollment = str(row.get('enrollment_no') or row.get('enrollment') or '').strip()
                name = str(row.get('name') or '').strip()
                email = str(row.get('email') or '').strip()
                if not enrollment or not name:
                    errors.append({'line': line, 'error': 'enrollment_no and name are required.'})
                    continue
                student, was_created = User.objects.get_or_create(
                    enrollment_no=enrollment,
                    defaults={'username': enrollment.lower(), 'name': name, 'email': email, 'user_type': 'student',
                              'department': str(row.get('department') or '').strip()},
                )
                if was_created:
                    if email:
                        # Email on file: send a "set your password" link through the
                        # same reset-token flow used for forgotten passwords, and
                        # leave the account with an unusable password until then.
                        student.set_unusable_password()
                        student.save(update_fields=['password'])
                        reset = PasswordResetToken.objects.create(
                            user=student, expires_at=timezone.now() + timedelta(days=7)
                        )
                        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset.token}"
                        send_mail(
                            'Welcome to Academia Pro — set your password',
                            f'An account was created for you (username: {student.username}). '
                            f'Set your password within 7 days using this link: {reset_url}',
                            None, [email], fail_silently=True,
                        )
                    else:
                        # No email on file: there is no channel to deliver a reset
                        # link, so issue a usable temporary password and hand it
                        # back to the faculty member importing the roster so they
                        # can share it out of band.
                        temp_password = get_random_string(10)
                        student.set_password(temp_password)
                        student.must_change_password = True
                        student.save(update_fields=['password', 'must_change_password'])
                        temp_credentials.append({
                            'enrollment_no': enrollment, 'username': student.username, 'temp_password': temp_password,
                        })
                    created += 1
                else:
                    updated += 1
                StudentExamAccess.objects.get_or_create(
                    exam=exam, student=student,
                    defaults={'temp_otp': StudentExamAccess.generate_otp(6), 'is_active': True},
                )
        except (UnicodeDecodeError, csv.Error) as error:
            return Response({'error': f'Invalid CSV: {error}'}, status=status.HTTP_400_BAD_REQUEST)
        audit(request, 'roster_csv_imported', exam, {'created_students': created, 'existing_students': updated})
        return Response({
            'created_students': created, 'existing_students': updated, 'errors': errors,
            'temp_credentials': temp_credentials,
        })


class ExamAppealView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, exam_id):
        qs = ExamAppeal.objects.filter(session__exam_id=exam_id).select_related('session__student')
        if request.user.user_type == 'faculty':
            exam = Exam.objects.filter(id=exam_id).first()
            if not exam or not faculty_can_review_exam(request.user, exam):
                return Response({'error': 'This assessment belongs to another department.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            qs = qs.filter(session__student=request.user)
        return Response({'appeals': [self._serialize(appeal, request.user.user_type == 'faculty') for appeal in qs]})

    def post(self, request, exam_id):
        if request.user.user_type != 'student':
            return Response({'error': 'Only students can submit appeals.'}, status=status.HTTP_403_FORBIDDEN)
        session = StudentExamSession.objects.filter(exam_id=exam_id, student=request.user).select_related('exam').first()
        if not session or not session.exam.results_released:
            return Response({'error': 'Appeals are available after results are released.'}, status=status.HTTP_400_BAD_REQUEST)
        reason = str(request.data.get('reason', '')).strip()
        if len(reason) < 10:
            return Response({'error': 'Please provide a reason of at least 10 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        appeal = ExamAppeal.objects.create(session=session, question_type=request.data.get('question_type', ''),
                                           question_id=request.data.get('question_id') or None, reason=reason,
                                           status='reviewing')
        # Route the ticket to whichever faculty actually checked this paper
        # (the one who verified the session's marks), not to every faculty
        # in the department — that just spams people who never touched it.
        # Before a session has been verified there is no "grader" yet, so
        # fall back to the exam's creator.
        reviewer = session.faculty_verified_by or session.exam.created_by
        notify(reviewer, 'appeal', f'New appeal: {session.exam.title}', f'{request.user.name} requested a review.', '/appeals')
        audit(request, 'appeal_created', appeal)
        return Response(self._serialize(appeal, False), status=status.HTTP_201_CREATED)

    def patch(self, request, exam_id, appeal_id):
        if request.user.user_type != 'faculty':
            return Response({'error': 'Faculty access required.'}, status=status.HTTP_403_FORBIDDEN)
        appeal = ExamAppeal.objects.filter(id=appeal_id, session__exam_id=exam_id).select_related('session__student').first()
        if not appeal:
            return Response({'error': 'Appeal not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not faculty_can_review_exam(request.user, appeal.session.exam):
            return Response({'error': 'This appeal belongs to another department.'}, status=status.HTTP_403_FORBIDDEN)
        new_status = request.data.get('status')
        if new_status not in dict(ExamAppeal.STATUS_CHOICES):
            return Response({'error': 'Choose a valid appeal status.'}, status=status.HTTP_400_BAD_REQUEST)
        response_text = str(request.data.get('faculty_response', appeal.faculty_response)).strip()
        if new_status == 'resolved' and not response_text:
            return Response({'error': 'Write a response for the student before resolving this appeal.'}, status=status.HTTP_400_BAD_REQUEST)
        appeal.status = new_status
        appeal.faculty_response = response_text
        if new_status in ('resolved', 'rejected'):
            appeal.resolved_by, appeal.resolved_at = request.user, timezone.now()
        appeal.save()
        notify(appeal.session.student, 'appeal', f'Appeal updated: {appeal.session.exam.title}', appeal.faculty_response or 'Your appeal status was updated.', '/appeals')
        audit(request, 'appeal_updated', appeal, {'status': new_status})
        return Response(self._serialize(appeal, True))

    @staticmethod
    def _serialize(appeal, include_student):
        data = {'id': appeal.id, 'question_type': appeal.question_type, 'question_id': appeal.question_id,
                'reason': appeal.reason, 'status': appeal.status, 'faculty_response': appeal.faculty_response,
                'created_at': appeal.created_at, 'updated_at': appeal.updated_at}
        if include_student:
            data['student'] = {'id': appeal.session.student_id, 'name': appeal.session.student.name,
                               'enrollment_no': appeal.session.student.enrollment_no}
        return data


class AppealsInboxView(views.APIView):
    """Cross-exam ticket inbox for students and department faculty."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExamAppeal.objects.select_related('session__student', 'session__exam').order_by('-updated_at')
        if request.user.user_type == 'student':
            qs = qs.filter(session__student=request.user)
        elif request.user.user_type == 'faculty':
            # Only tickets for papers this faculty actually checked (or,
            # before any grader was assigned, exams they created) — not every
            # appeal across the whole department.
            qs = qs.filter(
                Q(session__faculty_verified_by=request.user)
                | Q(session__faculty_verified_by__isnull=True, session__exam__created_by=request.user)
            ).distinct()
        else:
            qs = qs.none()
        return Response({'appeals': [ExamAppealView._serialize(item, request.user.user_type == 'faculty') | {
            'exam_id': item.session.exam_id, 'exam_title': item.session.exam.title,
        } for item in qs]})
