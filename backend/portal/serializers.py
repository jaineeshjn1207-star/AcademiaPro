from rest_framework import serializers
from .models import (
    User, Exam, StudentExamAccess, MCQQuestion, CodingProblem,
    ReferenceSolution, StudentExamSession, MCQResponse, CodingSubmission,
    FacultyNote, StudentNote, ProctorEvent, ProctorRecording
)

SAFE_ATTACHMENT_EXTENSIONS = {
    '.pdf', '.txt', '.md', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.csv', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.zip'
}
BLOCKED_ATTACHMENT_EXTENSIONS = {
    '.html', '.htm', '.svg', '.js', '.mjs', '.exe', '.bat', '.cmd', '.sh',
    '.php', '.py', '.jar', '.msi', '.scr', '.vbs'
}
MAX_NOTE_ATTACHMENT_SIZE = 20 * 1024 * 1024


def validate_safe_attachment(file_obj):
    if not file_obj:
        return file_obj
    import os
    name = getattr(file_obj, 'name', '') or ''
    ext = os.path.splitext(name.lower())[1]
    if getattr(file_obj, 'size', 0) > MAX_NOTE_ATTACHMENT_SIZE:
        raise serializers.ValidationError('Attachment is too large. Maximum allowed size is 20 MB.')
    if ext in BLOCKED_ATTACHMENT_EXTENSIONS or ext not in SAFE_ATTACHMENT_EXTENSIONS:
        raise serializers.ValidationError(
            'Unsupported or unsafe attachment type. Allowed: PDF, Office files, text/CSV, images, and ZIP.'
        )
    return file_obj


class UserSerializer(serializers.ModelSerializer):
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'name', 'enrollment_no', 'user_type', 'department', 'branch', 'email',
                  'is_blocked', 'blocked_reason', 'blocked_at', 'must_change_password', 'faculty_subjects']

    def get_user_type(self, obj):
        return 'admin' if getattr(obj, 'user_type', None) == 'admin' or obj.is_staff or obj.is_superuser else obj.user_type


class StudentExamAccessSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_enrollment = serializers.CharField(source='student.enrollment_no', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)

    class Meta:
        model = StudentExamAccess
        fields = ['id', 'exam', 'exam_title', 'student', 'student_name', 'student_enrollment', 'temp_otp', 'is_active', 'created_at', 'cleared_at']


class ReferenceSolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferenceSolution
        fields = ['id', 'title', 'language', 'code', 'logic_explanation']



class CodingProblemStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodingProblem
        fields = [
            'id', 'title', 'problem_statement', 'input_format', 'output_format',
            'sample_input', 'sample_output', 'marks', 'language'
        ]


class CodingProblemFacultySerializer(serializers.ModelSerializer):
    reference_solutions = ReferenceSolutionSerializer(many=True, read_only=True)

    class Meta:
        model = CodingProblem
        fields = [
            'id', 'title', 'problem_statement', 'input_format', 'output_format',
            'sample_input', 'sample_output', 'marks', 'language',
            'reference_solutions'
        ]


class MCQQuestionStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MCQQuestion
        fields = ['id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'question_type', 'marks', 'negative_marks']


class MCQQuestionFacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = MCQQuestion
        fields = ['id', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'question_type', 'correct_option', 'correct_options', 'marks', 'negative_marks']


class ExamSerializer(serializers.ModelSerializer):
    mcq_count = serializers.SerializerMethodField()
    coding_count = serializers.SerializerMethodField()
    is_live = serializers.SerializerMethodField()
    allocated_marks = serializers.SerializerMethodField()
    remaining_marks = serializers.SerializerMethodField()
    can_publish = serializers.SerializerMethodField()
    results_released = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'description', 'subject', 'audience', 'target_department', 'target_branch', 'phase', 'start_time', 'end_time', 'duration_minutes',
            'passing_marks', 'total_marks', 'is_active', 'content_locked',
            'results_published', 'results_published_at', 'results_released', 'requires_otp', 'created_at',
            'mcq_count', 'coding_count', 'is_live', 'allocated_marks', 'remaining_marks', 'can_publish',
            'enforce_fullscreen', 'block_shortcuts', 'block_copy_paste', 'require_screen_recording',
            'max_violations', 'auto_submit_on_violation',
        ]
        read_only_fields = ['created_at']

    def validate(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        duration = attrs.get('duration_minutes', getattr(self.instance, 'duration_minutes', None))
        total = attrs.get('total_marks', getattr(self.instance, 'total_marks', None))
        passing = attrs.get('passing_marks', getattr(self.instance, 'passing_marks', None))

        if start and end and end <= start:
            raise serializers.ValidationError({'end_time': 'Exam end time must be after the start time.'})
        if duration is not None and duration <= 0:
            raise serializers.ValidationError({'duration_minutes': 'Duration must be greater than zero.'})
        if total is not None and total <= 0:
            raise serializers.ValidationError({'total_marks': 'Total marks must be greater than zero.'})
        if passing is not None and total is not None and passing > total:
            raise serializers.ValidationError({'passing_marks': 'Passing marks cannot be greater than total marks.'})
        if start and end and duration is not None:
            window_minutes = (end - start).total_seconds() / 60
            if duration > window_minutes:
                raise serializers.ValidationError({'duration_minutes': 'Duration cannot exceed the exam window.'})
        return attrs

    def get_is_live(self, obj):
        return obj.is_exam_active()

    def get_mcq_count(self, obj):
        return obj.mcq_questions.count()

    def get_coding_count(self, obj):
        return obj.coding_problems.count()

    def get_allocated_marks(self, obj):
        total = sum(q.marks for q in obj.mcq_questions.all()) + sum(p.marks for p in obj.coding_problems.all())
        return float(total)

    def get_remaining_marks(self, obj):
        return max(0.0, float(obj.total_marks or 0) - self.get_allocated_marks(obj))

    def get_can_publish(self, obj):
        allocated = self.get_allocated_marks(obj)
        return allocated > 0 and abs(allocated - float(obj.total_marks or 0)) <= 0.001

    def get_results_released(self, obj):
        return bool(obj.results_released)


class MCQResponseSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    correct_option = serializers.CharField(source='question.correct_option', read_only=True)
    correct_options = serializers.ListField(source='question.correct_options', read_only=True)
    option_a = serializers.CharField(source='question.option_a', read_only=True)
    option_b = serializers.CharField(source='question.option_b', read_only=True)
    option_c = serializers.CharField(source='question.option_c', read_only=True)
    option_d = serializers.CharField(source='question.option_d', read_only=True)
    max_marks = serializers.FloatField(source='question.marks', read_only=True)
    negative_marks = serializers.FloatField(source='question.negative_marks', read_only=True)

    class Meta:
        model = MCQResponse
        fields = ['id', 'question', 'question_text', 'question_type', 'option_a', 'option_b', 'option_c', 'option_d',
                  'selected_option', 'selected_options', 'is_correct', 'marks_awarded', 'marks_overridden',
                  'correct_option', 'correct_options', 'max_marks', 'negative_marks']


class CodingSubmissionSerializer(serializers.ModelSerializer):
    max_marks = serializers.SerializerMethodField()
    problem_title = serializers.CharField(source='problem.title', read_only=True)
    problem_statement = serializers.CharField(source='problem.problem_statement', read_only=True)

    class Meta:
        model = CodingSubmission
        fields = [
            'id', 'problem', 'problem_title', 'problem_statement', 'language',
            'submitted_code', 'logic_status', 'marks_awarded', 'max_marks',
            'faculty_feedback', 'matched_reference',
            'reviewed_by_faculty', 'marks_overridden',
            'test_passed_count', 'test_total_count', 'hidden_failed_count',
            'failed_visible_tests', 'ai_detected_approach', 'ai_logic_summary',
            'ai_mistake_explanation', 'ai_corrected_code', 'ai_predicted_output', 'ai_debug_source',
        ]

    def get_max_marks(self, obj):
        return obj.problem.marks

    def _can_unlock_references(self, obj):
        request = self.context.get('request')
        is_faculty = bool(request and request.user.user_type == 'faculty')
        if is_faculty:
            return True

        needs_reference = obj.logic_status in ('incorrect', 'partial', 'pending')
        return obj.session.status == 'evaluated' and needs_reference and obj.session.exam.results_released

    def get_reference_unlock_available(self, obj):
        return self._can_unlock_references(obj)

    def get_reference_unlock_at(self, obj):
        return obj.session.exam.end_time

    def get_reference_solutions(self, obj):
        # Faculty can always audit references. Students see them only after the
        # whole exam window ends, so candidates still writing the exam cannot
        # receive leaked solutions from early submitters.
        if not self._can_unlock_references(obj):
            return []
        sols = list(obj.problem.reference_solutions.all())
        data = ReferenceSolutionSerializer(sols, many=True).data
        matched_title = (obj.matched_reference or '').strip()
        for d in data:
            d['is_closest_match'] = bool(matched_title) and d['title'] == matched_title
        # The reference solution closest to the student's own submitted logic
        # (as judged at evaluation time) is surfaced first, not just dumped
        # in creation order — that's the one most useful for them to read.
        data.sort(key=lambda d: not d['is_closest_match'])
        return data


class ProctorEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctorEvent
        fields = ['id', 'event_type', 'severity', 'details', 'created_at']


class ProctorRecordingSerializer(serializers.ModelSerializer):
    clip_url = serializers.SerializerMethodField()

    class Meta:
        model = ProctorRecording
        fields = ['id', 'event_type', 'details', 'clip_url', 'created_at']

    def get_clip_url(self, obj):
        if not obj.clip:
            return None
        request = self.context.get('request')
        url = obj.clip.url
        return request.build_absolute_uri(url) if request else url


class StudentExamSessionSerializer(serializers.ModelSerializer):
    total_marks = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    proctor_events = ProctorEventSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_enrollment = serializers.CharField(source='student.enrollment_no', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    mcq_responses = MCQResponseSerializer(many=True, read_only=True)
    coding_submissions = CodingSubmissionSerializer(many=True, read_only=True)

    class Meta:
        model = StudentExamSession
        fields = [
            'id', 'exam', 'exam_title', 'student', 'student_name', 'student_enrollment',
            'started_at', 'submitted_at', 'status', 'mcq_score', 'coding_score',
            'total_score', 'is_passed', 'mcq_responses', 'coding_submissions',
            'violation_count', 'is_auto_submitted', 'is_locked', 'is_ufm', 'ufm_reason',
            'faculty_verified', 'faculty_verified_at', 'faculty_verified_by',
            'total_marks', 'percentage', 'proctor_events',
        ]

    def get_total_marks(self, obj):
        return obj.exam.total_marks

    def get_percentage(self, obj):
        tm = obj.exam.total_marks or 0
        if not tm:
            return 0.0
        return round((obj.total_score / tm) * 100, 2)

    def to_representation(self, instance):
        """Hide marks, pass/fail and per-question verdicts from the student
        who owns this session until the exam's window has closed for
        everyone (Exam.results_released). Faculty always get the full
        picture. A caller can force full visibility regardless of timing by
        passing context={'reveal_override': True} — used only for the
        student's own immediate submit-confirmation response, which is
        never rendered by the frontend and is a receipt of their action
        rather than a "view results" surface.

        Conduct/status fields (submission status, violation history, UFM
        flag) are NOT gated here — a student already learns about those in
        real time during the exam itself, so hiding them again afterwards
        would just be confusing, not protective.
        """
        data = super().to_representation(instance)
        request = self.context.get('request')
        is_faculty = bool(request and getattr(request.user, 'user_type', None) == 'faculty')
        released = is_faculty or bool(self.context.get('reveal_override')) or instance.exam.results_released

        data['results_released'] = released
        data['exam_end_time'] = instance.exam.end_time

        if not released:
            for field in ('mcq_score', 'coding_score', 'total_score', 'percentage', 'is_passed'):
                data[field] = None
            data['mcq_responses'] = []
            data['coding_submissions'] = []
        return data


# ============================================================
#  NOTES SERIALIZERS
# ============================================================

class FacultyNoteSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.name', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True, default=None)
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()

    class Meta:
        model = FacultyNote
        fields = [
            'id', 'title', 'subject', 'description', 'content', 'attachment',
            'attachment_url', 'attachment_name', 'external_link', 'visibility',
            'department', 'exam', 'exam_title', 'is_published', 'is_pinned',
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['uploaded_by', 'created_at', 'updated_at']
        extra_kwargs = {'attachment': {'required': False, 'allow_null': True, 'write_only': True}}

    def validate_attachment(self, value):
        return validate_safe_attachment(value)

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url

    def get_attachment_name(self, obj):
        if not obj.attachment:
            return None
        return obj.attachment.name.split('/')[-1]


class StudentNoteSerializer(serializers.ModelSerializer):
    tag_list = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentNote
        fields = [
            'id', 'title', 'content', 'subject', 'tags', 'tag_list',
            'attachment', 'attachment_url', 'attachment_name',
            'color', 'is_pinned', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {'attachment': {'required': False, 'allow_null': True, 'write_only': True}}

    def validate_attachment(self, value):
        return validate_safe_attachment(value)

    def get_tag_list(self, obj):
        return obj.tag_list()

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return None
        request = self.context.get('request')
        url = obj.attachment.url
        return request.build_absolute_uri(url) if request else url

    def get_attachment_name(self, obj):
        if not obj.attachment:
            return None
        import re
        name = obj.attachment.name.split('/')[-1]
        return re.sub(r'_[A-Za-z0-9]{7}(?=\.[^.]+$)', '', name)
