from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .ai_tutor import AITutorChatView
from .views import (
    UnifiedLoginView, ForcePasswordChangeView, FacultyLoginView, StudentNormalLoginView, CurrentUserView,
    ExamViewSet, FacultyExamManagementView, CreateMCQView, CreateCodingProblemView,
    GenerateOTPsView, PublishExamView, StartExamView, RunCodeView, SubmitExamView, StudentExamResultView,
    EvaluateCodingSubmissionView, LeaderboardView, ResultsView, AnalyticsView, AnalyticsChartImageView, StudentSubmissionsListView,
    ExamRosterView, StudentExamAnalysisView, UpdateStudentMarksView, VerifyStudentSessionView, PublishResultsView,
    BlockedStudentsView, UnblockStudentView,
    # new
    ExamAutoSaveView, ProctorEventView, ProctorRecordingUploadView, ProctorReportView, MyExamsView,
    FacultyNoteViewSet, StudentNoteViewSet, NotesSubjectsView,
    PasswordResetRequestView, PasswordResetConfirmView, NotificationView,
    AuditLogView, AdminOverviewView, AdminUsersView, AdminUserDetailView, AdminUserPasswordResetView,
    StudentTrendView,
    QuestionQualityView,
    ResultPdfView,
    CloneExamView, BulkRosterImportView, ExamAppealView, AppealsInboxView,
    PracticeQuestionsView, PracticeSubmitView, ExamCalendarView, BulkMCQImportView,
)

router = DefaultRouter()
router.register(r'exams', ExamViewSet, basename='exam')
router.register(r'faculty-notes', FacultyNoteViewSet, basename='faculty-note')
router.register(r'my-notes', StudentNoteViewSet, basename='student-note')

urlpatterns = [
    # ---------- Auth ----------
    path('auth/login/', UnifiedLoginView.as_view(), name='unified-login'),
    path('auth/force-password-change/', ForcePasswordChangeView.as_view(), name='force-password-change'),
    path('auth/faculty/login/', FacultyLoginView.as_view(), name='faculty-login'),
    path('auth/student/login/', StudentNormalLoginView.as_view(), name='student-normal-login'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token-verify'),

    # ---------- Student ----------
    path('my-exams/', MyExamsView.as_view(), name='my-exams'),
    path('notes/subjects/', NotesSubjectsView.as_view(), name='notes-subjects'),
    path('ai-tutor/chat/', AITutorChatView.as_view(), name='ai-tutor-chat'),
    path('notifications/', NotificationView.as_view(), name='notifications'),
    path('appeals/', AppealsInboxView.as_view(), name='appeals-inbox'),
    path('audit-logs/', AuditLogView.as_view(), name='audit-logs'),
    path('admin/overview/', AdminOverviewView.as_view(), name='admin-overview'),
    path('admin/users/', AdminUsersView.as_view(), name='admin-users'),
    path('admin/users/<int:user_id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:user_id>/reset-password/', AdminUserPasswordResetView.as_view(), name='admin-reset-user-password'),
    path('my-progress/', StudentTrendView.as_view(), name='student-trend'),
    path('practice/questions/', PracticeQuestionsView.as_view(), name='practice-questions'),
    path('practice/submit/', PracticeSubmitView.as_view(), name='practice-submit'),
    path('exams/<int:exam_id>/question-quality/', QuestionQualityView.as_view(), name='question-quality'),
    path('exams/<int:exam_id>/result-card.pdf', ResultPdfView.as_view(), name='result-pdf'),
    path('exams/<int:exam_id>/calendar.ics', ExamCalendarView.as_view(), name='exam-calendar'),

    # ---------- Faculty exam management ----------
    path('exams/<int:exam_id>/manage/', FacultyExamManagementView.as_view(), name='exam-manage'),
    path('exams/<int:exam_id>/mcqs/', CreateMCQView.as_view(), name='create-mcq'),
    path('exams/<int:exam_id>/mcqs/bulk-import/', BulkMCQImportView.as_view(), name='bulk-import-mcqs'),
    path('exams/<int:exam_id>/mcqs/<int:mcq_id>/', CreateMCQView.as_view(), name='mcq-detail'),
    path('exams/<int:exam_id>/coding/', CreateCodingProblemView.as_view(), name='create-coding'),
    path('exams/<int:exam_id>/coding/<int:problem_id>/', CreateCodingProblemView.as_view(), name='coding-detail'),
    path('exams/<int:exam_id>/coding/<int:problem_id>/run/', RunCodeView.as_view(), name='run-code'),
    path('exams/<int:exam_id>/otps/', GenerateOTPsView.as_view(), name='generate-otps'),
    path('exams/<int:exam_id>/publish/', PublishExamView.as_view(), name='publish-exam'),
    path('exams/<int:exam_id>/roster/', ExamRosterView.as_view(), name='exam-roster'),
    path('exams/<int:exam_id>/publish-results/', PublishResultsView.as_view(), name='publish-results'),
    path('exams/<int:exam_id>/clone/', CloneExamView.as_view(), name='clone-exam'),
    path('exams/<int:exam_id>/roster/import/', BulkRosterImportView.as_view(), name='import-roster'),

    # ---------- Exam runtime ----------
    path('exams/<int:exam_id>/start/', StartExamView.as_view(), name='start-exam'),
    path('exams/<int:exam_id>/autosave/', ExamAutoSaveView.as_view(), name='autosave-exam'),
    path('exams/<int:exam_id>/proctor-event/', ProctorEventView.as_view(), name='proctor-event'),
    path('exams/<int:exam_id>/proctor-recording/', ProctorRecordingUploadView.as_view(), name='proctor-recording'),
    path('exams/<int:exam_id>/submit/', SubmitExamView.as_view(), name='submit-exam'),
    path('exams/<int:exam_id>/result/', StudentExamResultView.as_view(), name='exam-result'),
    path('exams/<int:exam_id>/appeals/', ExamAppealView.as_view(), name='exam-appeals'),
    path('exams/<int:exam_id>/appeals/<int:appeal_id>/', ExamAppealView.as_view(), name='exam-appeal-detail'),

    # ---------- Reporting ----------
    path('results/', ResultsView.as_view(), name='results'),
    path('exams/<int:exam_id>/leaderboard/', LeaderboardView.as_view(), name='exam-leaderboard'),
    path('exams/<int:exam_id>/analytics/', AnalyticsView.as_view(), name='exam-analytics'),
    path('exams/<int:exam_id>/analytics/chart/<str:filename>/', AnalyticsChartImageView.as_view(), name='exam-analytics-chart'),
    path('exams/<int:exam_id>/submissions/', StudentSubmissionsListView.as_view(), name='exam-submissions'),
    path('exams/<int:exam_id>/proctor-report/', ProctorReportView.as_view(), name='proctor-report'),
    path('exams/<int:exam_id>/students/<int:student_id>/analysis/', StudentExamAnalysisView.as_view(), name='student-analysis'),
    path('exams/<int:exam_id>/students/<int:student_id>/marks/', UpdateStudentMarksView.as_view(), name='update-marks'),
    path('exams/<int:exam_id>/students/<int:student_id>/verify/', VerifyStudentSessionView.as_view(), name='verify-session'),
    path('coding-submissions/<int:submission_id>/evaluate/', EvaluateCodingSubmissionView.as_view(), name='evaluate-coding'),

    # ---------- Unfair-means account locks ----------
    path('students/blocked/', BlockedStudentsView.as_view(), name='blocked-students'),
    path('students/<int:student_id>/unblock/', UnblockStudentView.as_view(), name='unblock-student'),

    path('', include(router.urls)),
]
