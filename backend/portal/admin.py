from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Exam, StudentExamAccess, MCQQuestion, CodingProblem,
    ReferenceSolution, CodingTestCase, StudentExamSession, MCQResponse, CodingSubmission,
    FacultyNote, StudentNote, ProctorEvent, ProctorRecording, PracticeQuestion
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'name', 'enrollment_no', 'user_type', 'department', 'is_active')
    list_filter = ('user_type', 'department', 'is_active')
    search_fields = ('username', 'name', 'enrollment_no', 'email')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Exam Portal Profile', {'fields': ('user_type', 'enrollment_no', 'name', 'department')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Exam Portal Profile', {'fields': ('user_type', 'enrollment_no', 'name', 'department')}),
    )


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_time', 'end_time', 'duration_minutes', 'total_marks', 'is_active', 'content_locked')
    list_filter = ('is_active', 'content_locked', 'enforce_fullscreen', 'requires_otp')
    search_fields = ('title',)


@admin.register(StudentExamAccess)
class StudentExamAccessAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'temp_otp', 'is_active', 'used_at', 'cleared_at')
    list_filter = ('is_active', 'exam')
    search_fields = ('student__enrollment_no', 'student__name')


@admin.register(MCQQuestion)
class MCQQuestionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'exam', 'correct_option', 'marks', 'negative_marks')
    list_filter = ('exam', 'correct_option')


class ReferenceSolutionInline(admin.StackedInline):
    model = ReferenceSolution
    extra = 1


@admin.register(CodingProblem)
class CodingProblemAdmin(admin.ModelAdmin):
    list_display = ('title', 'exam', 'marks')
    list_filter = ('exam',)
    inlines = [ReferenceSolutionInline]


@admin.register(StudentExamSession)
class StudentExamSessionAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'status', 'mcq_score', 'coding_score',
                    'total_score', 'is_passed', 'violation_count', 'is_auto_submitted')
    list_filter = ('status', 'is_passed', 'exam', 'is_auto_submitted')
    search_fields = ('student__enrollment_no', 'student__name')


@admin.register(CodingSubmission)
class CodingSubmissionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'logic_status', 'marks_awarded', 'reviewed_by_faculty')
    list_filter = ('logic_status', 'reviewed_by_faculty', 'language')


@admin.register(FacultyNote)
class FacultyNoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'visibility', 'uploaded_by', 'is_published', 'is_pinned', 'created_at')
    list_filter = ('visibility', 'is_published', 'is_pinned', 'subject')
    search_fields = ('title', 'subject', 'content')


@admin.register(StudentNote)
class StudentNoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'subject', 'color', 'is_pinned', 'updated_at')
    list_filter = ('color', 'is_pinned')
    search_fields = ('title', 'content', 'student__enrollment_no')


@admin.register(ProctorEvent)
class ProctorEventAdmin(admin.ModelAdmin):
    list_display = ('session', 'event_type', 'severity', 'created_at')
    list_filter = ('event_type', 'severity')


admin.site.register(ReferenceSolution)
admin.site.register(MCQResponse)

admin.site.site_header = "Academia Pro Administration"
admin.site.site_title = "Academia Pro Admin"
admin.site.index_title = "Examination & Notes Management"


@admin.register(ProctorRecording)
class ProctorRecordingAdmin(admin.ModelAdmin):
    list_display = ('session', 'event_type', 'created_at')
    list_filter = ('event_type',)
    search_fields = ('session__student__enrollment_no', 'session__student__name')


@admin.register(PracticeQuestion)
class PracticeQuestionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'topic', 'difficulty', 'correct_option', 'is_active')
    list_filter = ('topic', 'difficulty', 'is_active')
    search_fields = ('question_text', 'topic')

