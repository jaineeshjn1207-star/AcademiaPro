"""
Full regression suite for the Academia Pro exam portal.
Run:  python3 manage.py test portal -v 2
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from unittest.mock import patch

from .models import (
    User, Exam, StudentExamAccess, MCQQuestion, CodingProblem,
    ReferenceSolution, CodingTestCase, StudentExamSession, MCQResponse, CodingSubmission,
    FacultyNote, StudentNote, ProctorEvent, Notification, PracticeQuestion,
)
from .ai_code_evaluator import evaluate_code_ai_first
from .gemini_code_evaluator import _build_prompt
from .views import evaluate_coding_submissions_in_background


class BaseSetup(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.faculty = User.objects.create_user(
            username='prof_test', password='faculty123', name='Prof Test',
            user_type='faculty', department='CSE', email='prof@test.edu',
        )
        self.student = User.objects.create_user(
            username='en001', password='x', name='Test Student',
            user_type='student', enrollment_no='EN001', department='CSE',
        )
        self.student2 = User.objects.create_user(
            username='en002', password='x', name='Second Student',
            user_type='student', enrollment_no='EN002', department='ECE',
        )
        self.admin_user = User.objects.create_user(
            username='admin_test', password='admin123', name='Admin Test',
            user_type='admin', department='Administration', email='admin@test.edu',
            is_staff=True,
        )

        now = timezone.now()
        self.exam = Exam.objects.create(
            title='Test Exam', created_by=self.faculty,
            start_time=now - timedelta(minutes=10),
            end_time=now + timedelta(hours=2),
            duration_minutes=60, total_marks=100, passing_marks=40,
            max_violations=3,
        )

        self.q1 = MCQQuestion.objects.create(
            exam=self.exam, question_text='2+2?',
            option_a='3', option_b='4', option_c='5', option_d='6',
            correct_option='B', marks=10, negative_marks=2,
        )
        self.q2 = MCQQuestion.objects.create(
            exam=self.exam, question_text='Capital of India?',
            option_a='Mumbai', option_b='Chennai', option_c='New Delhi', option_d='Kolkata',
            correct_option='C', marks=10, negative_marks=2,
        )

        self.problem = CodingProblem.objects.create(
            exam=self.exam, title='Two Sum',
            problem_statement='Return indices of two numbers adding to target.',
            marks=80,
        )
        ReferenceSolution.objects.create(
            problem=self.problem, title='Hash Map O(N)', language='python',
            logic_explanation='Store complements in a dict.',
            code=(
                "def two_sum(nums, target):\n"
                "    seen = {}\n"
                "    for i, v in enumerate(nums):\n"
                "        c = target - v\n"
                "        if c in seen:\n"
                "            return [seen[c], i]\n"
                "        seen[v] = i\n"
                "    return []\n"
            ),
        )

        self.access = StudentExamAccess.objects.create(
            exam=self.exam, student=self.student, temp_otp='123456', is_active=True,
        )
        StudentExamAccess.objects.create(
            exam=self.exam, student=self.student2, temp_otp='654321', is_active=True,
        )

    # -- helpers ----------------------------------------------------------
    def login_student(self, enrollment='EN001', otp='123456'):
        # `otp` is accepted for backwards-compatible call sites (used later
        # against the exam-start endpoint) but no longer used for portal login.
        username = {'EN001': 'en001', 'EN002': 'en002'}.get(enrollment, enrollment.lower())
        res = self.client.post('/api/auth/student/login/',
                               {'username': username, 'password': 'x'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res.data

    def login_admin(self):
        res = self.client.post('/api/auth/login/', {'username': 'admin_test', 'password': 'admin123'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res

    def login_faculty(self):
        res = self.client.post('/api/auth/faculty/login/',
                               {'username': 'prof_test', 'password': 'faculty123'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res.data

    def close_exam_window(self, exam=None):
        """Move an exam's end_time into the past, simulating that its
        scheduled window has closed for every candidate. Several endpoints
        (results, leaderboard, analytics, dashboard) hide a student's own
        marks until this is true — tests that want to inspect the
        post-release view call this first."""
        exam = exam or self.exam
        exam.end_time = timezone.now() - timedelta(minutes=1)
        exam.results_published = True
        exam.results_published_at = timezone.now()
        exam.save(update_fields=['end_time', 'results_published', 'results_published_at'])
        StudentExamSession.objects.filter(exam=exam, status__in=['submitted', 'evaluated', 'ufm']).update(
            faculty_verified=True, faculty_verified_at=timezone.now()
        )
        return exam


# =====================================================================
class BranchScopedAccessTests(BaseSetup):

    def test_appeal_reviewers_are_selected_by_branch_not_department(self):
        same_branch_faculty = User.objects.create_user(
            username='prof_branch', password='x', name='Same Branch Faculty',
            user_type='faculty', branch='CE', department='CSE', email='branch@test.edu',
        )
        other_branch_faculty = User.objects.create_user(
            username='prof_other', password='x', name='Other Branch Faculty',
            user_type='faculty', branch='IT', department='CSE', email='other@test.edu',
        )
        self.exam.created_by = same_branch_faculty
        self.exam.target_branch = 'CE'
        self.exam.save(update_fields=['created_by', 'target_branch'])
        StudentExamSession.objects.create(
            exam=self.exam, student=self.student, status='evaluated',
            mcq_score=10, coding_score=0, total_score=10,
        )
        self.close_exam_window()

        self.client.force_authenticate(self.student)
        res = self.client.post(f'/api/exams/{self.exam.id}/appeals/', {'reason': 'Please review this result.'}, format='json')

        self.assertEqual(res.status_code, 201, res.data)
        recipients = list(Notification.objects.filter(link='/appeals').values_list('recipient_id', flat=True))
        self.assertIn(same_branch_faculty.id, recipients)
        self.assertNotIn(other_branch_faculty.id, recipients)


class AuthTests(BaseSetup):

    def test_student_normal_login(self):
        """Students sign in to the whole portal with a normal username/password —
        never with the temporary exam OTP, which only unlocks the exam room."""
        data = self.login_student()
        self.assertEqual(data['user']['enrollment_no'], 'EN001')
        self.assertEqual(data['user']['user_type'], 'student')
        self.assertNotIn('exam', data)

    def test_student_login_wrong_password_rejected(self):
        res = self.client.post('/api/auth/student/login/',
                               {'username': 'en001', 'password': 'wrong'}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_otp_login_endpoint_removed(self):
        """The old full-portal OTP login must no longer exist — OTP is only
        accepted on the exam room's start screen now."""
        res = self.client.post('/api/auth/student/otp-login/',
                               {'enrollment_no': 'EN001', 'otp': '123456'}, format='json')
        self.assertEqual(res.status_code, 404)

    def test_start_exam_wrong_otp_rejected(self):
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/start/',
                               {'temp_otp': '000000'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_start_exam_cleared_otp_rejected(self):
        self.access.is_active = False
        self.access.save()
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/start/',
                               {'temp_otp': '123456'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_faculty_login_and_role_guard(self):
        self.login_faculty()
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.data['user_type'], 'faculty')

    def test_student_cannot_use_faculty_login(self):
        res = self.client.post('/api/auth/faculty/login/',
                               {'username': 'en001', 'password': 'x'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_faculty_login_missing_fields(self):
        res = self.client.post('/api/auth/faculty/login/', {}, format='json')
        self.assertEqual(res.status_code, 400)


# =====================================================================
class ExamFlowTests(BaseSetup):

    def test_start_exam_returns_shuffled_paper(self):
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['mcqs']), 2)
        self.assertIn('remaining_seconds', res.data)
        self.assertIn('proctor_config', res.data)
        # Option text must still be one of the originals
        opts = {res.data['mcqs'][0][f'option_{k}'] for k in 'abcd'}
        self.assertEqual(len(opts), 4)

    def test_start_exam_payload_includes_mcq_question_type(self):
        """Regression: /start/ hand-builds the MCQ payload for per-student
        option shuffling and once dropped question_type entirely, silently
        making every multi-select question render as single-select."""
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        for q in res.data['mcqs']:
            self.assertIn('question_type', q)

    def test_multi_select_mcq_full_marks_for_exact_match(self):
        self.exam.total_marks += 6
        self.exam.save(update_fields=['total_marks'])
        multi_q = MCQQuestion.objects.create(
            exam=self.exam, question_text='Pick the primes',
            option_a='2', option_b='3', option_c='4', option_d='6',
            question_type='multi', correct_options=['A', 'B'], marks=6, negative_marks=2,
        )
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        self.assertIn('mcqs', start, start)
        payload_q = next(q for q in start['mcqs'] if q['id'] == multi_q.id)
        # translate real option letters -> whatever slot they were shuffled into
        correct_texts = {'2', '3'}
        selected_slots = [k[-1].upper() for k, v in payload_q.items() if k.startswith('option_') and v in correct_texts]

        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {str(multi_q.id): selected_slots}, 'coding_answers': {},
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        resp = MCQResponse.objects.get(session__student=self.student, question=multi_q)
        self.assertTrue(resp.is_correct)
        self.assertEqual(resp.marks_awarded, 6)
        self.assertEqual(sorted(resp.selected_options), ['A', 'B'])

    def test_multi_select_mcq_partial_selection_is_wrong(self):
        self.exam.total_marks += 6
        self.exam.save(update_fields=['total_marks'])
        multi_q = MCQQuestion.objects.create(
            exam=self.exam, question_text='Pick the primes',
            option_a='2', option_b='3', option_c='4', option_d='6',
            question_type='multi', correct_options=['A', 'B'], marks=6, negative_marks=2,
        )
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        self.assertIn('mcqs', start, start)
        payload_q = next(q for q in start['mcqs'] if q['id'] == multi_q.id)
        only_one_correct = [k[-1].upper() for k, v in payload_q.items() if k.startswith('option_') and v == '2']

        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {str(multi_q.id): only_one_correct}, 'coding_answers': {},
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        resp = MCQResponse.objects.get(session__student=self.student, question=multi_q)
        self.assertFalse(resp.is_correct)
        self.assertEqual(resp.marks_awarded, -2)  # partial selection is wrong, so negative marking applies

    def test_shuffle_is_stable_across_restarts(self):
        self.login_student()
        a = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        b = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        self.assertEqual([q['id'] for q in a['mcqs']], [q['id'] for q in b['mcqs']])
        self.assertEqual(a['mcqs'][0]['option_a'], b['mcqs'][0]['option_a'])

    def test_shuffled_option_answer_maps_back_correctly(self):
        """The critical bug: student picks the displayed slot; server must
        translate it back to the true option before grading."""
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)

        answers = {}
        for q in start['mcqs']:
            correct_text = MCQQuestion.objects.get(id=q['id']).get_correct_text = None
            real = MCQQuestion.objects.get(id=q['id'])
            true_text = {'A': real.option_a, 'B': real.option_b,
                         'C': real.option_c, 'D': real.option_d}[real.correct_option]
            # find which displayed slot holds the true answer text
            slot = next(k.upper() for k in 'abcd' if q[f'option_{k}'] == true_text)
            answers[str(q['id'])] = slot

        res = self.client.post(f'/api/exams/{self.exam.id}/submit/',
                               {'mcq_answers': answers, 'coding_answers': {}}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['session']['mcq_score'], 20.0)

    def test_unattempted_mcq_has_no_negative_marking(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/',
                               {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        self.assertEqual(res.data['session']['mcq_score'], 0.0)

    def test_total_score_never_negative(self):
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        # deliberately answer everything wrong
        answers = {}
        for q in start['mcqs']:
            real = MCQQuestion.objects.get(id=q['id'])
            true_text = {'A': real.option_a, 'B': real.option_b,
                         'C': real.option_c, 'D': real.option_d}[real.correct_option]
            wrong = next(k.upper() for k in 'abcd' if q[f'option_{k}'] != true_text)
            answers[str(q['id'])] = wrong
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/',
                               {'mcq_answers': answers, 'coding_answers': {}}, format='json')
        self.assertGreaterEqual(res.data['session']['mcq_score'], 0.0)

    def test_otp_cleared_after_submit(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/',
                         {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        self.access.refresh_from_db()
        self.assertFalse(self.access.is_active)
        self.assertIsNotNone(self.access.cleared_at)

    def test_double_submit_rejected(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/',
                         {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/',
                               {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_cannot_start_before_window(self):
        self.exam.start_time = timezone.now() + timedelta(hours=1)
        self.exam.end_time = timezone.now() + timedelta(hours=3)
        self.exam.save()
        self.access.is_active = True
        self.access.save()
        self.client.force_authenticate(user=self.student)
        res = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_cannot_start_after_exam_window_closes(self):
        self.exam.start_time = timezone.now() - timedelta(hours=2)
        self.exam.end_time = timezone.now() - timedelta(seconds=1)
        self.exam.save(update_fields=['start_time', 'end_time'])
        self.client.force_authenticate(user=self.student)
        res = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertIn('closed', res.data['error'].lower())

    def test_cannot_resume_after_duration_deadline(self):
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.assertEqual(start.status_code, 200, start.data)
        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        session.started_at = timezone.now() - timedelta(minutes=self.exam.duration_minutes + 1)
        session.save(update_fields=['started_at'])
        res = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertIn('expired', res.data['error'].lower())

    def test_after_deadline_autosave_and_run_code_are_closed(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        session.started_at = timezone.now() - timedelta(minutes=self.exam.duration_minutes + 1)
        session.save(update_fields=['started_at'])

        autosave = self.client.post(f'/api/exams/{self.exam.id}/autosave/', {'mcq_answers': {}}, format='json')
        self.assertEqual(autosave.status_code, 403)
        run = self.client.post(f'/api/exams/{self.exam.id}/coding/{self.problem.id}/run/', {'code': 'print(1)'}, format='json')
        self.assertEqual(run.status_code, 403)

    def test_after_deadline_submit_uses_last_server_autosave_not_fresh_answers(self):
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        q = start['mcqs'][0]
        real = MCQQuestion.objects.get(id=q['id'])
        true_text = {'A': real.option_a, 'B': real.option_b,
                     'C': real.option_c, 'D': real.option_d}[real.correct_option]
        correct_slot = next(k.upper() for k in 'abcd' if q[f'option_{k}'] == true_text)
        wrong_slot = next(k.upper() for k in 'abcd' if k.upper() != correct_slot)

        self.client.post(f'/api/exams/{self.exam.id}/autosave/', {'mcq_answers': {str(q['id']): correct_slot}}, format='json')
        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        session.started_at = timezone.now() - timedelta(minutes=self.exam.duration_minutes + 1)
        session.save(update_fields=['started_at'])

        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'mcq_answers': {str(q['id']): wrong_slot}}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['session']['mcq_score'], real.marks)
        self.assertTrue(res.data['auto_submitted'])

    def test_autosave_and_recovery(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/autosave/', {
            'mcq_answers': {str(self.q1.id): 'B'},
            'coding_answers': {str(self.problem.id): {'code': 'draft', 'language': 'python'}},
        }, format='json')
        self.assertEqual(res.status_code, 200)
        again = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        self.assertEqual(again['mcq_draft'], {str(self.q1.id): 'B'})

    def test_submit_falls_back_to_server_draft(self):
        """If the client crashes and submits nothing, saved drafts are graded."""
        self.login_student()
        start = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json').data
        q = start['mcqs'][0]
        real = MCQQuestion.objects.get(id=q['id'])
        true_text = {'A': real.option_a, 'B': real.option_b,
                     'C': real.option_c, 'D': real.option_d}[real.correct_option]
        slot = next(k.upper() for k in 'abcd' if q[f'option_{k}'] == true_text)

        self.client.post(f'/api/exams/{self.exam.id}/autosave/',
                         {'mcq_answers': {str(q['id']): slot}}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {}, format='json')
        self.assertEqual(res.data['session']['mcq_score'], real.marks)

    @patch('portal.ai_code_evaluator.evaluate_with_gemini', return_value=None)
    def test_gemini_unavailable_submission_is_pending_even_if_old_tests_exist(self, mock_gemini):
        """Retired hidden/visible test-case rows do not grade anymore;
        without Gemini the submission is pending faculty review.
        """
        CodingTestCase.objects.create(
            problem=self.problem,
            input_data='2 7 11 15\n9',
            expected_output='0 1',
            is_hidden=True,
        )
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        wrong_code = "def solution():\n    array=[1,2,3,4]\n    for i in array:\n        print(i)\nsolution()\n"
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {},
            'coding_answers': {str(self.problem.id): {'code': wrong_code, 'language': 'python'}},
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        evaluate_coding_submissions_in_background(session.id)
        sub = CodingSubmission.objects.get(problem=self.problem, session__student=self.student)
        self.assertEqual(sub.marks_awarded, 0.0)
        self.assertEqual(sub.logic_status, 'pending')
        self.assertIn('faculty review', sub.faculty_feedback.lower())
        self.assertEqual(sub.test_passed_count, 0)
        self.assertEqual(sub.test_total_count, 0)
        self.assertEqual(sub.hidden_failed_count, 0)
        self.assertTrue(sub.ai_mistake_explanation)

    @patch('portal.ai_code_evaluator.evaluate_with_gemini', return_value=None)
    def test_old_test_case_rows_do_not_create_local_fallback_grade(self, mock_gemini):
        """Old test-case rows may exist in upgraded databases, but grading
        remains Gemini-only; if Gemini is unavailable the result is pending.
        """
        now = timezone.now()
        exam = Exam.objects.create(
            title='Addition Logic Exam', created_by=self.faculty,
            start_time=now - timedelta(minutes=5), end_time=now + timedelta(hours=1),
            duration_minutes=30, total_marks=26, passing_marks=10,
            is_active=False, content_locked=False,
        )
        problem = CodingProblem.objects.create(
            exam=exam, title='addition', problem_statement='add 2 numbers',
            marks=26, language='python', sample_input='2 3', sample_output='5',
        )
        cases = [
            ('2 3', '5', False),
            ('10 25', '35', True),
            ('-5 12', '7', True),
            ('-7 -8', '-15', True),
            ('24 -98', '-74', True),
        ]
        for inp, out, hidden in cases:
            CodingTestCase.objects.create(problem=problem, input_data=inp, expected_output=out, is_hidden=hidden)
        exam.is_active = True
        exam.content_locked = True
        exam.save(update_fields=['is_active', 'content_locked'])
        StudentExamAccess.objects.create(exam=exam, student=self.student, temp_otp='999999', is_active=True)

        self.client.force_authenticate(user=self.student)
        start = self.client.post(f'/api/exams/{exam.id}/start/', {'temp_otp': '999999'}, format='json')
        self.assertEqual(start.status_code, 200, start.data)
        code = 'a=24\nb=-98\nprint(a+b)\n'
        res = self.client.post(f'/api/exams/{exam.id}/submit/', {
            'mcq_answers': {},
            'coding_answers': {str(problem.id): {'code': code, 'language': 'python'}},
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        session = StudentExamSession.objects.get(exam=exam, student=self.student)
        evaluate_coding_submissions_in_background(session.id)
        sub = CodingSubmission.objects.get(problem=problem, session__student=self.student)
        self.assertEqual(sub.marks_awarded, 0.0)
        self.assertEqual(sub.logic_status, 'pending')
        self.assertEqual(sub.evaluated_by, 'gemini-unavailable')
        self.assertIn('faculty review', sub.faculty_feedback.lower())

    def test_result_hidden_while_exam_still_open(self):
        """A student must not see their own marks while the exam window is
        still open for other candidates — even though their own session
        has already been evaluated server-side."""
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/',
                         {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        res = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'evaluated')
        self.assertFalse(res.data['results_released'])
        self.assertIsNone(res.data['percentage'])
        self.assertIsNone(res.data['total_score'])
        self.assertIsNone(res.data['is_passed'])
        self.assertEqual(res.data['mcq_responses'], [])
        self.assertEqual(res.data['coding_submissions'], [])

    def test_result_visible_after_exam_window_closes(self):
        """Once the exam's scheduled window has closed for everyone, the
        same student can see their marks."""
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/',
                         {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        self.close_exam_window()
        res = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['results_released'])
        self.assertIn('percentage', res.data)
        self.assertIsNotNone(res.data['percentage'])

    def test_submit_receipt_shows_score_even_before_window_closes(self):
        """The immediate response to the student's own submit action is a
        receipt of that action (never rendered by the frontend) and is
        exempt from the results-release gate, unlike every other way of
        reading the same session afterwards."""
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/',
                               {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        self.assertEqual(res.data['session']['status'], 'evaluated')
        self.assertIsNotNone(res.data['session']['percentage'])

    def test_my_exams_endpoint(self):
        self.login_student()
        res = self.client.get('/api/my-exams/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['exams']), 1)
        self.assertEqual(res.data['exams'][0]['state'], 'live')

    def test_my_exams_hides_score_until_window_closes(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/',
                         {'mcq_answers': {}, 'coding_answers': {}}, format='json')

        res = self.client.get('/api/my-exams/')
        card = res.data['exams'][0]
        self.assertEqual(card['state'], 'completed')
        self.assertFalse(card['results_released'])
        self.assertIsNone(card['total_score'])
        self.assertIsNone(card['is_passed'])

        self.close_exam_window()
        res = self.client.get('/api/my-exams/')
        card = res.data['exams'][0]
        self.assertTrue(card['results_released'])
        self.assertIsNotNone(card['total_score'])


# =====================================================================
class ProctoringTests(BaseSetup):

    def test_violation_is_recorded_and_counted(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/proctor-event/',
                               {'event_type': 'fullscreen_exit', 'details': 'exited'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['violation_count'], 1)
        self.assertEqual(res.data['severity'], 'high')
        self.assertFalse(res.data['must_auto_submit'])
        self.assertEqual(ProctorEvent.objects.count(), 1)

    def test_low_severity_events_do_not_count(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/proctor-event/',
                               {'event_type': 'contextmenu'}, format='json')
        self.assertEqual(res.data['violation_count'], 0)
        self.assertFalse(res.data['counted'])

    def test_auto_submit_triggers_at_limit(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        last = None
        for _ in range(3):
            last = self.client.post(f'/api/exams/{self.exam.id}/proctor-event/',
                                    {'event_type': 'tab_switch'}, format='json')
        self.assertEqual(last.data['violation_count'], 3)
        self.assertTrue(last.data['must_auto_submit'])

    def test_ufm_voids_marks_blocks_account_and_rejects_relogin(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        last = None
        for _ in range(3):
            last = self.client.post(f'/api/exams/{self.exam.id}/proctor-event/',
                                    {'event_type': 'tab_switch'}, format='json')
        self.assertTrue(last.data['is_ufm'])
        self.assertTrue(last.data['blocked'])

        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        self.assertEqual(session.status, 'ufm')
        self.assertTrue(session.is_ufm)
        self.assertEqual(session.total_score, 0)
        self.assertEqual(session.mcq_score, 0)
        self.assertEqual(session.coding_score, 0)

        self.student.refresh_from_db()
        self.assertTrue(self.student.is_blocked)

        # the still-valid access token is rejected on the very next request
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, 403)
        self.assertTrue(res.data.get('blocked'))

        # re-login is rejected too, even with the correct password
        self.client.credentials()
        res = self.client.post('/api/auth/student/login/', {'username': 'en001', 'password': 'x'}, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertTrue(res.data.get('blocked'))

    def test_faculty_cannot_view_or_unblock_student(self):
        self.student.is_blocked = True
        self.student.blocked_reason = 'test lock'
        self.student.save()

        self.login_faculty()
        res = self.client.get('/api/students/blocked/')
        self.assertEqual(res.status_code, 403)
        res = self.client.post(f'/api/students/{self.student.id}/unblock/')
        self.assertEqual(res.status_code, 403)
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_blocked)

    def test_admin_can_unblock_student(self):
        self.student.is_blocked = True
        self.student.blocked_reason = 'test lock'
        self.student.save()

        self.login_admin()
        res = self.client.get('/api/students/blocked/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

        res = self.client.post(f'/api/students/{self.student.id}/unblock/')
        self.assertEqual(res.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_blocked)

        self.client.credentials()
        res = self.client.post('/api/auth/student/login/', {'username': 'en001', 'password': 'x'}, format='json')
        self.assertEqual(res.status_code, 200)

    def test_auto_submitted_flag_persisted(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {}, 'coding_answers': {},
            'auto_submitted': True, 'reason': 'Violation limit reached',
        }, format='json')
        self.assertTrue(res.data['auto_submitted'])
        s = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        self.assertTrue(s.is_auto_submitted)
        self.assertTrue(ProctorEvent.objects.filter(event_type='auto_submit').exists())

    def test_admin_proctor_report(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/proctor-event/',
                         {'event_type': 'blur'}, format='json')
        self.client.credentials()
        self.login_faculty()
        # Proctor reports are admin-only; faculty is rejected.
        res = self.client.get(f'/api/exams/{self.exam.id}/proctor-report/')
        self.assertEqual(res.status_code, 403)
        self.client.credentials()
        self.login_admin()
        res = self.client.get(f'/api/exams/{self.exam.id}/proctor-report/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['report'][0]['violation_count'], 1)

    def test_invalid_event_type_is_sanitised(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/proctor-event/',
                               {'event_type': 'hack_the_planet'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(ProctorEvent.objects.first().event_type, 'other')


# =====================================================================
class GeminiOnlyEvaluatorTests(BaseSetup):
    def test_empty_submission_is_incorrect_without_calling_any_fallback(self):
        r = evaluate_code_ai_first('', 'python', self.problem, list(self.problem.reference_solutions.all()))
        self.assertEqual(r['logic_status'], 'incorrect')
        self.assertEqual(r['marks_awarded'], 0.0)
        self.assertEqual(r['source'], 'gemini-unavailable')

    @patch('portal.ai_code_evaluator.evaluate_with_gemini', return_value=None)
    def test_gemini_unavailable_is_pending_for_faculty_review(self, mock_gemini):
        problem = CodingProblem.objects.create(
            exam=self.exam,
            title='Pandas functions',
            problem_statement='read a csv file and display it; display a seaborn heatmap graph pass corr() in it; remove all null values from the dataset',
            marks=15,
            language='python',
        )
        code = (
            'import pandas as pd\n'
            'import seaborn as sns\n'
            'df = pd.read_csv("iris.csv")\n'
            'sns.heatmap(df.corr())\n'
            'df = df.dropna()\n'
            'print(df)\n'
        )
        r = evaluate_code_ai_first(code, 'python', problem, [])
        self.assertEqual(r['logic_status'], 'pending')
        self.assertEqual(r['marks_awarded'], 0.0)
        self.assertEqual(r['source'], 'gemini-unavailable')
        self.assertIn('faculty review', r['feedback'].lower())

    def test_gemini_prompt_has_language_specific_guidance_for_all_languages(self):
        problem = CodingProblem.objects.create(
            exam=self.exam, title='Prompt Test', problem_statement='Build feature', marks=5, language='python'
        )
        prompts = {lang: _build_prompt('print("x")', lang, problem, [], 5) for lang in ['python', 'javascript', 'cpp', 'java']}
        self.assertIn('pandas', prompts['python'].lower())
        self.assertIn('react', prompts['javascript'].lower())
        self.assertIn('c++17', prompts['cpp'].lower())
        self.assertIn('public Main'.lower(), prompts['java'].lower())
        self.assertIn('preserve', prompts['javascript'].lower())



# =====================================================================
class ReferenceUnlockTests(BaseSetup):

    def _submit(self, code, finish_exam=True):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {},
            'coding_answers': {str(self.problem.id): {'code': code, 'language': 'python'}},
        }, format='json')
        session = StudentExamSession.objects.get(exam=self.exam, student=self.student)
        evaluate_coding_submissions_in_background(session.id)
        if finish_exam:
            self.close_exam_window()
        return self.client.get(f'/api/exams/{self.exam.id}/result/').data


    def test_result_and_references_locked_until_exam_window_finishes(self):
        """While the exam is still open, a student sees none of their own
        marks or verdicts — not just reference solutions. This is the same
        results_released gate applied consistently everywhere, rather than
        the reference-solution-only version this test used to check."""
        data = self._submit("print('wrong logic')", finish_exam=False)
        self.assertFalse(data['results_released'])
        self.assertIsNone(data['total_score'])
        self.assertEqual(data['coding_submissions'], [])
        self.assertEqual(data['mcq_responses'], [])

    def test_references_unlocked_when_logic_wrong_after_exam_ends(self):
        data = self._submit("x = 1\ny = 2\nz = x + y\nprint('nothing useful here at all')")
        self.assertTrue(data['results_released'])
        sub = data['coding_submissions'][0]
        self.assertIn(sub['logic_status'], ('incorrect', 'partial', 'pending'))
        self.assertTrue(sub['reference_unlock_available'])
        self.assertGreater(len(sub['reference_solutions']), 0)
        self.assertIn('logic_explanation', sub['reference_solutions'][0])

    @patch('portal.ai_code_evaluator.evaluate_with_gemini', return_value=None)
    def test_model_unavailable_marks_for_review_and_unlocks_references_after_exam_ends(self, mock_gemini):
        data = self._submit('def two_sum(nums, target):\n    return []\n')
        sub = data['coding_submissions'][0]
        self.assertEqual(sub['logic_status'], 'pending')
        self.assertIn('faculty review', sub['faculty_feedback'].lower())
        self.assertTrue(sub['reference_unlock_available'])
        self.assertGreater(len(sub['reference_solutions']), 0)

    def test_faculty_always_sees_references(self):
        self._submit('def two_sum(nums, target):\n    return []\n')
        self.client.credentials()
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/submissions/')
        self.assertGreater(len(res.data[0]['coding_submissions'][0]['reference_solutions']), 0)


# =====================================================================
class FacultyNotesTests(BaseSetup):

    def test_faculty_can_create_note(self):
        self.login_faculty()
        res = self.client.post('/api/faculty-notes/', {
            'title': 'Graph Theory Basics', 'subject': 'Algorithms',
            'content': 'BFS and DFS traversal fundamentals.', 'visibility': 'all',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['uploaded_by_name'], 'Prof Test')

    def test_faculty_can_upload_attachment(self):
        self.login_faculty()
        f = SimpleUploadedFile('unit1.txt', b'Unit 1 lecture notes', content_type='text/plain')
        res = self.client.post('/api/faculty-notes/', {
            'title': 'Unit 1 PDF', 'subject': 'DS', 'attachment': f, 'visibility': 'all',
        }, format='multipart')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNotNone(res.data['attachment_url'])
        self.assertTrue(res.data['attachment_name'].startswith('unit1'))

    def test_student_can_read_but_not_create(self):
        FacultyNote.objects.create(title='Public Note', uploaded_by=self.faculty,
                                   visibility='all', is_published=True)
        self.login_student()
        res = self.client.get('/api/faculty-notes/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

        deny = self.client.post('/api/faculty-notes/', {'title': 'Hack'}, format='json')
        self.assertEqual(deny.status_code, 403)

    def test_unpublished_note_hidden_from_students(self):
        FacultyNote.objects.create(title='Draft', uploaded_by=self.faculty,
                                   visibility='all', is_published=False)
        self.login_student()
        self.assertEqual(len(self.client.get('/api/faculty-notes/').data), 0)

    def test_department_visibility_filter(self):
        FacultyNote.objects.create(title='CSE Only', uploaded_by=self.faculty,
                                   visibility='department', department='CSE', is_published=True)
        self.login_student('EN001', '123456')          # CSE student
        self.assertEqual(len(self.client.get('/api/faculty-notes/').data), 1)

        self.client.credentials()
        self.login_student('EN002', '654321')          # ECE student
        self.assertEqual(len(self.client.get('/api/faculty-notes/').data), 0)

    def test_exam_scoped_visibility(self):
        FacultyNote.objects.create(title='Exam Candidates', uploaded_by=self.faculty,
                                   visibility='exam', exam=self.exam, is_published=True)
        self.login_student()
        self.assertEqual(len(self.client.get('/api/faculty-notes/').data), 1)

    def test_search_filter(self):
        FacultyNote.objects.create(title='Sorting Algorithms', uploaded_by=self.faculty,
                                   visibility='all', is_published=True, content='merge sort')
        FacultyNote.objects.create(title='Graph Theory', uploaded_by=self.faculty,
                                   visibility='all', is_published=True)
        self.login_student()
        res = self.client.get('/api/faculty-notes/?search=sorting')
        self.assertEqual(len(res.data), 1)

    def test_faculty_cannot_edit_another_faculty_note(self):
        other = User.objects.create_user(username='prof2', password='p', name='Other',
                                         user_type='faculty')
        note = FacultyNote.objects.create(title='Theirs', uploaded_by=other, visibility='all')
        self.login_faculty()
        res = self.client.patch(f'/api/faculty-notes/{note.id}/', {'title': 'Stolen'}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_pinned_notes_sort_first(self):
        FacultyNote.objects.create(title='Normal', uploaded_by=self.faculty, visibility='all')
        FacultyNote.objects.create(title='Pinned', uploaded_by=self.faculty,
                                   visibility='all', is_pinned=True)
        self.login_student()
        res = self.client.get('/api/faculty-notes/')
        self.assertEqual(res.data[0]['title'], 'Pinned')


# =====================================================================
class StudentNotesTests(BaseSetup):

    def test_crud_lifecycle(self):
        self.login_student()
        created = self.client.post('/api/my-notes/', {
            'title': 'My Revision', 'content': 'Big-O rules', 'color': 'blue', 'tags': 'a, b',
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['tag_list'], ['a', 'b'])
        nid = created.data['id']

        upd = self.client.patch(f'/api/my-notes/{nid}/', {'is_pinned': True}, format='json')
        self.assertTrue(upd.data['is_pinned'])

        self.assertEqual(self.client.delete(f'/api/my-notes/{nid}/').status_code, 204)
        self.assertEqual(StudentNote.objects.count(), 0)

    def test_notes_are_private_between_students(self):
        StudentNote.objects.create(student=self.student, title='Private A')
        StudentNote.objects.create(student=self.student2, title='Private B')

        self.login_student('EN001', '123456')
        res = self.client.get('/api/my-notes/')
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['title'], 'Private A')

    def test_student_can_upload_private_note_attachment(self):
        self.login_student()
        f = SimpleUploadedFile('formula-sheet.txt', b'a^2+b^2', content_type='text/plain')
        created = self.client.post('/api/my-notes/', {
            'title': 'Formula Sheet', 'content': 'See attached', 'attachment': f,
        }, format='multipart')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertIsNotNone(created.data['attachment_url'])
        self.assertEqual(created.data['attachment_name'], 'formula-sheet.txt')

    def test_student_note_rejects_unsafe_attachment(self):
        self.login_student()
        f = SimpleUploadedFile('xss.html', b'<script>alert(1)</script>', content_type='text/html')
        created = self.client.post('/api/my-notes/', {
            'title': 'Unsafe', 'attachment': f,
        }, format='multipart')
        self.assertEqual(created.status_code, 400)
        self.assertIn('attachment', created.data)

    def test_cannot_read_another_students_note_by_id(self):
        theirs = StudentNote.objects.create(student=self.student2, title='Secret')
        self.login_student('EN001', '123456')
        self.assertEqual(self.client.get(f'/api/my-notes/{theirs.id}/').status_code, 404)

    def test_faculty_cannot_access_student_notebook(self):
        self.login_faculty()
        self.assertEqual(self.client.get('/api/my-notes/').status_code, 403)

    def test_search_personal_notes(self):
        StudentNote.objects.create(student=self.student, title='Sliding Window', tags='pattern')
        StudentNote.objects.create(student=self.student, title='Recursion')
        self.login_student()
        self.assertEqual(len(self.client.get('/api/my-notes/?search=sliding').data), 1)
        self.assertEqual(len(self.client.get('/api/my-notes/?search=pattern').data), 1)

    def test_subjects_endpoint(self):
        StudentNote.objects.create(student=self.student, title='N', subject='Algorithms')
        FacultyNote.objects.create(title='F', uploaded_by=self.faculty, subject='DBMS',
                                   visibility='all', is_published=True)
        self.login_student()
        res = self.client.get('/api/notes/subjects/')
        self.assertIn('Algorithms', res.data['my_subjects'])
        self.assertIn('DBMS', res.data['faculty_subjects'])


# =====================================================================
class FacultyManagementTests(BaseSetup):

    def test_create_mcq_validation(self):
        self.exam.total_marks = 120
        self.exam.is_active = False
        self.exam.save(update_fields=['total_marks', 'is_active'])
        self.login_faculty()
        bad = self.client.post(f'/api/exams/{self.exam.id}/mcqs/',
                               {'question_text': 'Incomplete'}, format='json')
        self.assertEqual(bad.status_code, 400)

        bad_opt = self.client.post(f'/api/exams/{self.exam.id}/mcqs/', {
            'question_text': 'Q', 'option_a': '1', 'option_b': '2',
            'option_c': '3', 'option_d': '4', 'correct_option': 'Z',
        }, format='json')
        self.assertEqual(bad_opt.status_code, 400)

        ok = self.client.post(f'/api/exams/{self.exam.id}/mcqs/', {
            'question_text': 'Q', 'option_a': '1', 'option_b': '2',
            'option_c': '3', 'option_d': '4', 'correct_option': 'c', 'marks': 5,
        }, format='json')
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.data['correct_option'], 'C')


    def test_cannot_allocate_marks_beyond_exam_total(self):
        self.exam.is_active = False
        self.exam.save(update_fields=['is_active'])
        self.login_faculty()
        res = self.client.post(f'/api/exams/{self.exam.id}/mcqs/', {
            'question_text': 'Too expensive', 'option_a': '1', 'option_b': '2',
            'option_c': '3', 'option_d': '4', 'correct_option': 'A', 'marks': 1,
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('exceed', res.data['error'].lower())

        res2 = self.client.post(f'/api/exams/{self.exam.id}/coding/', {
            'title': 'Extra problem', 'problem_statement': 'Solve it', 'marks': 5,
        }, format='json')
        self.assertEqual(res2.status_code, 400)
        self.assertIn('exceed', res2.data['error'].lower())

    def test_new_exam_requires_publish_after_exact_mark_allocation(self):
        self.login_faculty()
        now = timezone.now()
        created = self.client.post('/api/exams/', {
            'title': 'Publish Gate Exam',
            'start_time': now - timedelta(minutes=5),
            'end_time': now + timedelta(hours=1),
            'duration_minutes': 45,
            'total_marks': 80,
            'passing_marks': 32,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        exam = Exam.objects.get(id=created.data['id'])
        self.assertFalse(exam.is_active)

        # A one-mark question is allowed, but the exam is not publishable/startable yet.
        q = self.client.post(f'/api/exams/{exam.id}/mcqs/', {
            'question_text': 'One mark', 'option_a': '1', 'option_b': '2',
            'option_c': '3', 'option_d': '4', 'correct_option': 'A', 'marks': 1,
        }, format='json')
        self.assertEqual(q.status_code, 201, q.data)
        incomplete = self.client.post(f'/api/exams/{exam.id}/publish/', {}, format='json')
        self.assertEqual(incomplete.status_code, 400)
        self.assertIn('remaining: 79', incomplete.data['error'])

        fill = self.client.post(f'/api/exams/{exam.id}/coding/', {
            'title': 'Remaining', 'problem_statement': 'Solve it', 'marks': 79,
        }, format='json')
        self.assertEqual(fill.status_code, 201, fill.data)
        published = self.client.post(f'/api/exams/{exam.id}/publish/', {}, format='json')
        self.assertEqual(published.status_code, 200, published.data)
        exam.refresh_from_db()
        self.assertTrue(exam.is_active)

    def test_otps_auto_generated_on_exam_create_and_publish(self):
        self.login_faculty()
        now = timezone.now()
        created = self.client.post('/api/exams/', {
            'title': 'Auto OTP Exam',
            'start_time': now - timedelta(minutes=5),
            'end_time': now + timedelta(hours=1),
            'duration_minutes': 45,
            'total_marks': 1,
            'passing_marks': 1,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        exam = Exam.objects.get(id=created.data['id'])
        self.assertEqual(StudentExamAccess.objects.filter(exam=exam, is_active=True).count(), 2)
        first_codes = set(StudentExamAccess.objects.filter(exam=exam).values_list('temp_otp', flat=True))
        self.assertTrue(all(code and len(code) == 6 for code in first_codes))

        late_student = User.objects.create_user(
            username='en003', password='x', name='Late Student',
            user_type='student', enrollment_no='EN003', department='CSE',
        )
        q = self.client.post(f'/api/exams/{exam.id}/mcqs/', {
            'question_text': 'Ready', 'option_a': '1', 'option_b': '2',
            'option_c': '3', 'option_d': '4', 'correct_option': 'A', 'marks': 1,
        }, format='json')
        self.assertEqual(q.status_code, 201, q.data)
        published = self.client.post(f'/api/exams/{exam.id}/publish/', {}, format='json')
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(StudentExamAccess.objects.filter(exam=exam, is_active=True).count(), 3)
        self.assertTrue(StudentExamAccess.objects.filter(exam=exam, student=late_student, is_active=True).exists())
        # Publishing should not regenerate already-issued active OTPs.
        after_codes = set(StudentExamAccess.objects.filter(exam=exam, student__in=[self.student, self.student2]).values_list('temp_otp', flat=True))
        self.assertEqual(first_codes, after_codes)

    def test_generic_exam_patch_cannot_bypass_publish_lock(self):
        self.login_faculty()
        now = timezone.now()
        created = self.client.post('/api/exams/', {
            'title': 'Bypass Attempt Exam',
            'start_time': now - timedelta(minutes=5),
            'end_time': now + timedelta(hours=1),
            'duration_minutes': 45,
            'total_marks': 10,
            'passing_marks': 4,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        exam_id = created.data['id']
        res = self.client.patch(f'/api/exams/{exam_id}/', {'is_active': True}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('publish', res.data['error'].lower())
        res2 = self.client.patch(f'/api/exams/{exam_id}/', {'content_locked': True}, format='json')
        self.assertEqual(res2.status_code, 400)

    def test_published_exam_content_is_locked(self):
        self.login_faculty()
        now = timezone.now()
        exam = Exam.objects.create(
            title='Locked Published Exam', created_by=self.faculty,
            start_time=now - timedelta(minutes=5), end_time=now + timedelta(hours=1),
            duration_minutes=45, total_marks=2, passing_marks=1, is_active=False,
        )
        q = MCQQuestion.objects.create(
            exam=exam, question_text='One mark', option_a='1', option_b='2',
            option_c='3', option_d='4', correct_option='A', marks=1,
        )
        problem = CodingProblem.objects.create(
            exam=exam, title='One mark code', problem_statement='Print ok',
            sample_output='ok', marks=1, language='python',
        )
        sol = ReferenceSolution.objects.create(
            problem=problem, title='Ref', language='python', code='print("ok")', logic_explanation='Print ok',
        )
        CodingTestCase.objects.create(problem=problem, input_data='', expected_output='ok', is_hidden=True)

        published = self.client.post(f'/api/exams/{exam.id}/publish/', {}, format='json')
        self.assertEqual(published.status_code, 200, published.data)
        exam.refresh_from_db()
        self.assertTrue(exam.content_locked)

        attempts = [
            self.client.post(f'/api/exams/{exam.id}/mcqs/', {
                'question_text': 'New', 'option_a': '1', 'option_b': '2',
                'option_c': '3', 'option_d': '4', 'correct_option': 'A', 'marks': 1,
            }, format='json'),
            self.client.delete(f'/api/exams/{exam.id}/mcqs/{q.id}/'),
            self.client.post(f'/api/exams/{exam.id}/coding/', {
                'title': 'New code', 'problem_statement': 'Solve', 'marks': 1,
            }, format='json'),
            self.client.delete(f'/api/exams/{exam.id}/coding/{problem.id}/'),
            self.client.post(f'/api/coding-problems/{problem.id}/solutions/', {
                'title': 'New ref', 'code': 'print("ok")', 'logic_explanation': 'x',
            }, format='json'),
            self.client.delete(f'/api/coding-problems/{problem.id}/solutions/{sol.id}/'),
        ]
        for res in attempts:
            self.assertEqual(res.status_code, 400, getattr(res, 'data', None))
            self.assertIn('locked', res.data['error'].lower())

    def test_student_cannot_start_active_exam_with_incomplete_marks(self):
        now = timezone.now()
        exam = Exam.objects.create(
            title='Incomplete Active Exam', created_by=self.faculty,
            start_time=now - timedelta(minutes=5), end_time=now + timedelta(hours=1),
            duration_minutes=45, total_marks=80, passing_marks=32, is_active=True,
        )
        MCQQuestion.objects.create(
            exam=exam, question_text='Only one mark',
            option_a='1', option_b='2', option_c='3', option_d='4',
            correct_option='A', marks=1,
        )
        StudentExamAccess.objects.create(exam=exam, student=self.student, temp_otp='999999', is_active=True)

        normal_login = self.client.post('/api/auth/student/login/',
                                        {'username': 'en001', 'password': 'x'}, format='json')
        self.assertEqual(normal_login.status_code, 200, normal_login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {normal_login.data['access']}")
        start = self.client.post(f'/api/exams/{exam.id}/start/', {'temp_otp': '999999'}, format='json')
        self.assertEqual(start.status_code, 403)
        self.assertIn('remaining: 79', start.data['error'])


    def test_results_require_faculty_verification_and_publish_button(self):
        # Student submits; closing time alone should not release results.
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {'mcq_answers': {}, 'coding_answers': {}}, format='json')
        self.exam.end_time = timezone.now() - timedelta(minutes=1)
        self.exam.save(update_fields=['end_time'])

        result = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertFalse(result.data['results_released'])
        self.assertEqual(result.data['coding_submissions'], [])

        self.client.credentials()
        self.login_faculty()
        blocked = self.client.post(f'/api/exams/{self.exam.id}/publish-results/', {}, format='json')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('unverified', blocked.data['error'].lower())

        verify = self.client.post(f'/api/exams/{self.exam.id}/students/{self.student.id}/verify/', {}, format='json')
        self.assertEqual(verify.status_code, 200, verify.data)
        publish = self.client.post(f'/api/exams/{self.exam.id}/publish-results/', {}, format='json')
        self.assertEqual(publish.status_code, 200, publish.data)

        self.client.credentials()
        self.login_student()
        released = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertTrue(released.data['results_released'])
        self.assertIn('coding_submissions', released.data)

    def test_add_and_delete_reference_solution(self):
        self.exam.is_active = False
        self.exam.save(update_fields=['is_active'])
        self.login_faculty()
        res = self.client.post(f'/api/coding-problems/{self.problem.id}/solutions/', {
            'title': 'Sorting approach', 'code': 'nums.sort()', 'language': 'python',
            'logic_explanation': 'Sort then two pointers',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        sid = res.data['id']
        self.assertEqual(
            self.client.delete(f'/api/coding-problems/{self.problem.id}/solutions/{sid}/').status_code, 204)

    def test_reference_solution_requires_code(self):
        self.exam.is_active = False
        self.exam.save(update_fields=['is_active'])
        self.login_faculty()
        res = self.client.post(f'/api/coding-problems/{self.problem.id}/solutions/',
                               {'title': 'No code'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_generate_and_clear_otps(self):
        self.login_faculty()
        gen = self.client.post(f'/api/exams/{self.exam.id}/otps/', {}, format='json')
        self.assertEqual(gen.status_code, 200)
        self.assertEqual(len(gen.data['otps']), 2)

        self.client.delete(f'/api/exams/{self.exam.id}/otps/')
        self.assertEqual(StudentExamAccess.objects.filter(exam=self.exam, is_active=True).count(), 0)

    def test_faculty_override_clamps_marks(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {},
            'coding_answers': {str(self.problem.id): {'code': 'pass', 'language': 'python'}},
        }, format='json')
        sub = CodingSubmission.objects.first()

        self.client.credentials()
        self.login_faculty()
        res = self.client.post(f'/api/coding-submissions/{sub.id}/evaluate/', {
            'logic_status': 'correct', 'marks_awarded': 9999,
        }, format='json')
        self.assertEqual(res.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.marks_awarded, self.problem.marks)
        self.assertTrue(sub.reviewed_by_faculty)

    def test_override_rejects_bad_status(self):
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'coding_answers': {str(self.problem.id): {'code': 'pass'}}}, format='json')
        sub = CodingSubmission.objects.first()
        self.client.credentials()
        self.login_faculty()
        res = self.client.post(f'/api/coding-submissions/{sub.id}/evaluate/',
                               {'logic_status': 'perfect'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_update_marks_clamps_mcq_override_to_question_range(self):
        """Regression: UpdateStudentMarksView clamped coding overrides but
        initially forgot to clamp MCQ overrides the same way, letting a
        10-mark question be set to 9999."""
        self.login_student()
        self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {
            'mcq_answers': {}, 'coding_answers': {},
        }, format='json')
        resp = MCQResponse.objects.filter(session__student=self.student, question=self.q1).first()

        self.client.credentials()
        self.login_faculty()
        res = self.client.patch(f'/api/exams/{self.exam.id}/students/{self.student.id}/marks/',
                                {'mcq_overrides': {str(resp.id): 9999}}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        resp.refresh_from_db()
        self.assertEqual(resp.marks_awarded, self.q1.marks)  # clamped to the question's max, not 9999
        self.assertTrue(resp.marks_overridden)

        # negative side is clamped too — can't go below -negative_marks
        res = self.client.patch(f'/api/exams/{self.exam.id}/students/{self.student.id}/marks/',
                                {'mcq_overrides': {str(resp.id): -9999}}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        resp.refresh_from_db()
        self.assertEqual(resp.marks_awarded, -self.q1.negative_marks)

    def test_student_cannot_reach_faculty_endpoints(self):
        self.login_student()
        for url in (f'/api/exams/{self.exam.id}/manage/',
                    f'/api/exams/{self.exam.id}/submissions/',
                    f'/api/exams/{self.exam.id}/proctor-report/'):
            self.assertEqual(self.client.get(url).status_code, 403, url)


# =====================================================================
class ReportingTests(BaseSetup):

    def _evaluate_both(self):
        for student, otp, score in ((self.student, '123456', 90), (self.student2, '654321', 50)):
            s = StudentExamSession.objects.create(
                exam=self.exam, student=student, status='evaluated',
                mcq_score=score / 2, coding_score=score / 2, total_score=score,
                is_passed=score >= 40, submitted_at=timezone.now(),
            )
            s.save()
        self.close_exam_window()

    def test_leaderboard_ranking_and_self_flag(self):
        self._evaluate_both()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/')
        board = res.data['leaderboard']
        self.assertEqual(board[0]['total_score'], 90)
        self.assertEqual(board[0]['rank'], 1)
        self.assertEqual(board[1]['rank'], 2)
        self.assertTrue(board[0]['is_you'])
        self.assertEqual(res.data['my_rank'], 1)

    def test_leaderboard_ties_share_rank(self):
        for student in (self.student, self.student2):
            StudentExamSession.objects.create(
                exam=self.exam, student=student, status='evaluated',
                total_score=70, is_passed=True, submitted_at=timezone.now())
        self.close_exam_window()
        self.login_student()
        board = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data['leaderboard']
        self.assertEqual(board[0]['rank'], board[1]['rank'])

    def test_analytics_payload(self):
        self._evaluate_both()
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/analytics/')
        self.assertEqual(res.data['total_appeared'], 2)
        self.assertEqual(res.data['highest_score'], 90)
        self.assertEqual(res.data['lowest_score'], 50)
        self.assertEqual(res.data['avg_score'], 70)
        self.assertEqual(len(res.data['question_stats']), 2)

    def test_analytics_with_no_submissions(self):
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/analytics/')
        self.assertEqual(res.data['total_appeared'], 0)
        self.assertEqual(res.data['avg_score'], 0)

    def test_leaderboard_404_for_missing_exam(self):
        self.login_faculty()
        self.assertEqual(self.client.get('/api/exams/99999/leaderboard/').status_code, 404)


# =====================================================================
class SecurityTests(BaseSetup):

    def test_all_endpoints_require_auth(self):
        for url in ('/api/auth/me/', '/api/my-exams/', '/api/faculty-notes/',
                    '/api/my-notes/', f'/api/exams/{self.exam.id}/leaderboard/'):
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_student_cannot_create_exam(self):
        self.login_student()
        res = self.client.post('/api/exams/', {
            'title': 'Fake', 'start_time': timezone.now(), 'end_time': timezone.now(),
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_correct_option_never_leaked_to_student(self):
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/start/', {'temp_otp': '123456'}, format='json')
        for q in res.data['mcqs']:
            self.assertNotIn('correct_option', q)


# =====================================================================
class LeaderboardPrivacyTests(BaseSetup):
    """Students must never see another student's marks."""

    def _seed(self):
        StudentExamSession.objects.create(
            exam=self.exam, student=self.student, status='evaluated',
            mcq_score=20, coding_score=70, total_score=90,
            is_passed=True, submitted_at=timezone.now())
        StudentExamSession.objects.create(
            exam=self.exam, student=self.student2, status='evaluated',
            mcq_score=10, coding_score=40, total_score=50,
            is_passed=True, submitted_at=timezone.now())
        self.close_exam_window()

    def test_student_sees_own_row_in_full(self):
        self._seed()
        self.login_student()
        board = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data['leaderboard']
        mine = next(r for r in board if r['is_you'])
        self.assertEqual(mine['total_score'], 90)
        self.assertEqual(mine['student_name'], 'Test Student')
        self.assertFalse(mine['is_masked'])

    def test_student_cannot_see_other_marks(self):
        self._seed()
        self.login_student()
        board = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data['leaderboard']
        others = [r for r in board if not r['is_you']]
        self.assertTrue(others)
        for row in others:
            self.assertTrue(row['is_masked'])
            self.assertIsNone(row['total_score'])
            self.assertIsNone(row['mcq_score'])
            self.assertIsNone(row['coding_score'])
            self.assertIsNone(row['percentage'])
            self.assertIsNone(row['enrollment_no'])
            self.assertIsNone(row['is_passed'])

    def test_other_student_real_name_never_serialised(self):
        self._seed()
        self.login_student()
        raw = str(self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data)
        self.assertNotIn('Second Student', raw)
        self.assertNotIn('EN002', raw)

    def test_rank_still_correct_when_masked(self):
        self._seed()
        self.login_student()
        data = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data
        self.assertEqual(data['my_rank'], 1)
        self.assertEqual([r['rank'] for r in data['leaderboard']], [1, 2])
        self.assertTrue(data['is_masked_view'])

    def test_cohort_context_exposed_without_identities(self):
        self._seed()
        self.login_student()
        cohort = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data['cohort']
        self.assertEqual(cohort['highest_score'], 90)
        self.assertEqual(cohort['average_score'], 70)
        self.assertEqual(cohort['percentile'], 50.0)

    def test_faculty_sees_everything(self):
        self._seed()
        self.login_faculty()
        data = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/').data
        self.assertFalse(data['is_masked_view'])
        for row in data['leaderboard']:
            self.assertFalse(row['is_masked'])
            self.assertIsNotNone(row['total_score'])
        names = {r['student_name'] for r in data['leaderboard']}
        self.assertIn('Second Student', names)

    def test_student_cannot_read_another_students_result(self):
        self._seed()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertEqual(res.data['student_enrollment'], 'EN001')


# =====================================================================
class AnalyticsChartTests(BaseSetup):
    """Chart-ready series must be present, correct and privacy-safe."""

    def _seed(self):
        for student, total in ((self.student, 90), (self.student2, 30)):
            s = StudentExamSession.objects.create(
                exam=self.exam, student=student, status='evaluated',
                mcq_score=total / 2, coding_score=total / 2, total_score=total,
                is_passed=total >= 40, submitted_at=timezone.now())
            MCQResponse.objects.create(session=s, question=self.q1,
                                       selected_option='B', is_correct=True, marks_awarded=10)
            MCQResponse.objects.create(session=s, question=self.q2,
                                       selected_option='A', is_correct=False, marks_awarded=0)
            CodingSubmission.objects.create(
                session=s, problem=self.problem, submitted_code='x',
                logic_status='correct' if total > 50 else 'incorrect',
                marks_awarded=80 if total > 50 else 0)
        self.close_exam_window()

    def test_distribution_buckets_every_candidate(self):
        self._seed()
        self.login_faculty()
        d = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data
        self.assertEqual(sum(b['count'] for b in d['score_distribution']), 2)
        self.assertEqual(len(d['score_distribution']), 5)

    def test_question_stats_shape(self):
        self._seed()
        self.login_faculty()
        qs = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data['question_stats']
        self.assertEqual(len(qs), 2)
        self.assertEqual(qs[0]['label'], 'Q1')
        self.assertEqual(qs[0]['correct_responses'], 2)
        self.assertEqual(qs[0]['accuracy_percent'], 100.0)
        self.assertEqual(qs[1]['accuracy_percent'], 0.0)
        # correct + incorrect must reconcile with the total
        for q in qs:
            self.assertEqual(q['correct_responses'] + q['incorrect_responses'], q['total_responses'])

    def test_answer_key_hidden_from_students(self):
        self._seed()
        self.login_student()
        qs = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data['question_stats']
        for q in qs:
            self.assertIsNone(q['correct_option'])

    def test_answer_key_visible_to_faculty(self):
        self._seed()
        self.login_faculty()
        qs = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data['question_stats']
        self.assertEqual(qs[0]['correct_option'], 'B')

    def test_student_gets_only_own_scores(self):
        self._seed()
        self.login_student()
        d = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data
        self.assertEqual(d['my_scores']['total_score'], 90)
        raw = str(d)
        self.assertNotIn('Second Student', raw)
        self.assertNotIn('EN002', raw)

    def test_faculty_has_no_my_scores(self):
        self._seed()
        self.login_faculty()
        self.assertIsNone(self.client.get(f'/api/exams/{self.exam.id}/analytics/').data['my_scores'])

    def test_section_and_verdict_series(self):
        self._seed()
        self.login_faculty()
        d = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data
        sections = {s['section'] for s in d['section_comparison']}
        self.assertEqual(sections, {'MCQ', 'Coding'})
        verdicts = {v['status']: v['count'] for v in d['coding_status_breakdown']}
        self.assertEqual(verdicts.get('correct'), 1)
        self.assertEqual(verdicts.get('incorrect'), 1)

    def test_problem_stats_series(self):
        self._seed()
        self.login_faculty()
        ps = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data['problem_stats']
        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0]['submissions'], 2)
        self.assertEqual(ps[0]['correct'], 1)

    def test_median_and_aggregates(self):
        self._seed()
        self.login_faculty()
        d = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data
        self.assertEqual(d['median_score'], 60.0)
        self.assertEqual(d['highest_score'], 90)
        self.assertEqual(d['lowest_score'], 30)
        self.assertEqual(d['total_marks'], 100)

    def test_empty_state_has_all_chart_keys(self):
        self.login_faculty()
        d = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data
        for key in ('score_distribution', 'question_stats', 'section_comparison',
                    'coding_status_breakdown', 'total_marks', 'median_score'):
            self.assertIn(key, d)
        self.assertEqual(d['total_appeared'], 0)


# =====================================================================
class ResultsLockTests(BaseSetup):
    """Marks, verdicts, ranks and aggregate stats must stay hidden from
    students until Exam.results_released — i.e. until the exam's scheduled
    window has closed for every candidate, not just the one asking.
    Faculty are never gated by this. Covers every surface that reveals a
    score: the result page, the dashboard (see ExamFlowTests), the
    leaderboard, analytics, and the cross-exam results list."""

    def _seed_session(self, student=None, total_score=90):
        student = student or self.student
        return StudentExamSession.objects.create(
            exam=self.exam, student=student, status='evaluated',
            mcq_score=total_score / 2, coding_score=total_score / 2,
            total_score=total_score, is_passed=total_score >= 40,
            submitted_at=timezone.now(),
        )

    # -- leaderboard ------------------------------------------------------
    def test_leaderboard_locked_for_student_while_exam_open(self):
        self._seed_session()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['results_released'])
        self.assertEqual(res.data['leaderboard'], [])
        self.assertIsNone(res.data['my_rank'])
        self.assertNotIn('cohort', res.data)

    def test_leaderboard_unlocked_for_student_after_exam_ends(self):
        self._seed_session()
        self.close_exam_window()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/')
        self.assertTrue(res.data['results_released'])
        self.assertEqual(len(res.data['leaderboard']), 1)

    def test_leaderboard_never_locked_for_faculty(self):
        self._seed_session()
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/leaderboard/')
        self.assertTrue(res.data['results_released'])
        self.assertEqual(len(res.data['leaderboard']), 1)

    # -- analytics ----------------------------------------------------------
    def test_analytics_locked_for_student_while_exam_open(self):
        self._seed_session()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/analytics/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['results_released'])
        self.assertNotIn('my_scores', res.data)
        self.assertNotIn('question_stats', res.data)
        self.assertNotIn('chart_images', res.data)

    def test_analytics_open_for_faculty_while_exam_ongoing(self):
        """Faculty can monitor analytics live, mid-exam — only students are gated."""
        self._seed_session()
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/analytics/')
        self.assertTrue(res.data['results_released'])
        self.assertEqual(res.data['total_appeared'], 1)

    # -- cross-exam results list ("All Results") --------------------------
    def test_results_list_hides_score_while_exam_open(self):
        self._seed_session()
        self.login_student()
        row = self.client.get('/api/results/').data['results'][0]
        self.assertFalse(row['results_released'])
        self.assertIsNone(row['total_score'])
        self.assertIsNone(row['is_passed'])

    def test_results_list_reveals_score_after_exam_ends(self):
        self._seed_session()
        self.close_exam_window()
        self.login_student()
        row = self.client.get('/api/results/').data['results'][0]
        self.assertTrue(row['results_released'])
        self.assertEqual(row['total_score'], 90)

    def test_results_list_faculty_never_locked(self):
        self._seed_session()
        self.login_faculty()
        row = self.client.get('/api/results/').data['results'][0]
        self.assertTrue(row['results_released'])
        self.assertEqual(row['total_score'], 90)

    def test_results_list_score_filter_does_not_leak_locked_rows(self):
        """A min_score filter must not silently reveal a still-locked score
        by making the row disappear or appear based on it — the row should
        survive the filter either way while it's locked."""
        self._seed_session(total_score=95)
        self.login_student()
        self.assertEqual(len(self.client.get('/api/results/?min_score=0').data['results']), 1)
        self.assertEqual(len(self.client.get('/api/results/?min_score=99').data['results']), 1)


# =====================================================================
class ProductOperationsTests(BaseSetup):
    """Coverage for the self-service / faculty-ops additions: password
    reset, question bank, notifications (incl. link correctness), audit
    log, exam cloning, bulk roster import, appeals, student trend,
    question quality, the result PDF, and per-account login throttling."""

    def _seed_released_session(self, student=None, total_score=90):
        student = student or self.student
        session = StudentExamSession.objects.create(
            exam=self.exam, student=student, status='evaluated',
            mcq_score=total_score / 2, coding_score=total_score / 2,
            total_score=total_score, is_passed=total_score >= 40,
            submitted_at=timezone.now(), faculty_verified=True, faculty_verified_at=timezone.now(),
        )
        self.close_exam_window()
        return session

    # -- password reset -----------------------------------------------
    def test_password_reset_email_links_to_frontend_not_api_host(self):
        """Regression: reset_url used to be built from request.get_host(),
        which is this API's own domain — not where the React /reset-password
        route actually lives when frontend and backend are separate
        deployments. It must use settings.FRONTEND_URL instead."""
        from django.conf import settings
        from django.core import mail
        self.student.email = 'student@test.edu'
        self.student.save(update_fields=['email'])
        self.client.post('/api/auth/password-reset/', {'identifier': 'en001'}, format='json')
        self.assertTrue(mail.outbox, 'Expected a reset email to be sent.')
        body = mail.outbox[-1].body
        self.assertIn(f'{settings.FRONTEND_URL}/reset-password?token=', body)
        self.assertNotIn('testserver', body)

    def test_password_reset_full_lifecycle(self):
        self.student.email = 'student@test.edu'
        self.student.save(update_fields=['email'])
        res = self.client.post('/api/auth/password-reset/', {'identifier': 'en001'}, format='json')
        self.assertEqual(res.status_code, 200)
        from .models import PasswordResetToken
        token = PasswordResetToken.objects.filter(user=self.student).latest('created_at')
        confirm = self.client.post('/api/auth/password-reset/confirm/',
                                    {'token': token.token, 'password': 'BrandNewPass123'}, format='json')
        self.assertEqual(confirm.status_code, 200, confirm.data)
        # Old password no longer works, new one does.
        stale = self.client.post('/api/auth/student/login/', {'username': 'en001', 'password': 'x'}, format='json')
        self.assertEqual(stale.status_code, 401)
        fresh = self.client.post('/api/auth/student/login/', {'username': 'en001', 'password': 'BrandNewPass123'}, format='json')
        self.assertEqual(fresh.status_code, 200)

    def test_password_reset_unknown_identifier_gives_generic_response(self):
        """No account enumeration: an unknown identifier still returns 200
        with the same generic message as a real one."""
        res = self.client.post('/api/auth/password-reset/', {'identifier': 'nobody-here'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('If an account matches', res.data['message'])

    def test_password_reset_token_is_single_use(self):
        self.student.email = 'student@test.edu'
        self.student.save(update_fields=['email'])
        self.client.post('/api/auth/password-reset/', {'identifier': 'en001'}, format='json')
        from .models import PasswordResetToken
        token = PasswordResetToken.objects.filter(user=self.student).latest('created_at')
        first = self.client.post('/api/auth/password-reset/confirm/', {'token': token.token, 'password': 'FirstPass123'}, format='json')
        self.assertEqual(first.status_code, 200)
        second = self.client.post('/api/auth/password-reset/confirm/', {'token': token.token, 'password': 'SecondPass123'}, format='json')
        self.assertEqual(second.status_code, 400)

    # -- question bank ---------------------------------------------------
    def test_question_bank_full_mcq_payload_can_be_used_to_create_an_exam_question(self):
        """Regression: question bank items used to only ever store a bare
        title, with no way to actually use them in an exam. A full MCQ
        payload (options + correct answer) must round-trip and be directly
        usable to create a real MCQQuestion on an exam."""
        self.login_faculty()
        self.exam.is_active = False
        self.exam.total_marks = 200
        self.exam.save(update_fields=['is_active', 'total_marks'])
        payload = {
            'question_text': 'What does CPU stand for?',
            'option_a': 'Central Processing Unit', 'option_b': 'Computer Personal Unit',
            'option_c': 'Central Program Utility', 'option_d': 'Core Processing Unicode',
            'correct_option': 'A',
        }
        create = self.client.post('/api/question-bank/', {'kind': 'mcq', 'title': payload['question_text'], 'payload': payload}, format='json')
        self.assertEqual(create.status_code, 201, create.data)
        stored_payload = create.data['payload']

        add = self.client.post(f'/api/exams/{self.exam.id}/mcqs/', {
            'question_text': stored_payload['question_text'],
            'option_a': stored_payload['option_a'], 'option_b': stored_payload['option_b'],
            'option_c': stored_payload['option_c'], 'option_d': stored_payload['option_d'],
            'question_type': 'single', 'correct_option': stored_payload['correct_option'], 'correct_options': [],
            'marks': 4,
        }, format='json')
        self.assertEqual(add.status_code, 201, add.data)
        self.assertTrue(self.exam.mcq_questions.filter(question_text='What does CPU stand for?').exists())

    def test_question_bank_crud_is_owner_scoped(self):
        self.login_faculty()
        create = self.client.post('/api/question-bank/', {'kind': 'mcq', 'title': 'Reusable Q'}, format='json')
        self.assertEqual(create.status_code, 201, create.data)
        listing = self.client.get('/api/question-bank/')
        self.assertEqual(len(listing.data['items']), 1)

        other_faculty = User.objects.create_user(username='prof_other', password='x', name='Other Prof', user_type='faculty')
        self.client.credentials()
        self.client.force_authenticate(user=other_faculty)
        other_listing = self.client.get('/api/question-bank/')
        self.assertEqual(len(other_listing.data['items']), 0)

    def test_question_bank_rejects_invalid_kind(self):
        self.login_faculty()
        res = self.client.post('/api/question-bank/', {'kind': 'essay', 'title': 'Nope'}, format='json')
        self.assertEqual(res.status_code, 400)

    # -- notifications -----------------------------------------------------
    def test_notifications_list_and_mark_read(self):
        from .models import Notification
        Notification.objects.create(recipient=self.student, notification_type='system', title='Hi', body='Body')
        self.login_student()
        res = self.client.get('/api/notifications/')
        self.assertEqual(res.data['unread_count'], 1)
        self.client.patch('/api/notifications/', {}, format='json')
        res2 = self.client.get('/api/notifications/')
        self.assertEqual(res2.data['unread_count'], 0)

    def test_result_published_notification_links_to_real_route(self):
        """Regression: the results-published notification used to point at
        the nonexistent /exam-result/<id> path instead of /exam/<id>/result."""
        session = self._seed_released_session()
        self.login_faculty()
        self.client.post(f'/api/exams/{self.exam.id}/students/{self.student.id}/verify/', {}, format='json')
        self.client.post(f'/api/exams/{self.exam.id}/publish-results/', {}, format='json')
        from .models import Notification
        note = Notification.objects.filter(recipient=self.student, notification_type='result').latest('created_at')
        self.assertEqual(note.link, f'/exam/{self.exam.id}/result')

    def test_appeal_notification_links_to_real_routes(self):
        """Regression: appeal notifications used to point at nonexistent
        /manage-exam/<id> and /exam-result/<id> paths."""
        self._seed_released_session()
        self.login_student()
        create = self.client.post(f'/api/exams/{self.exam.id}/appeals/',
                                   {'reason': 'I believe question 2 was ambiguous.'}, format='json')
        self.assertEqual(create.status_code, 201, create.data)
        from .models import Notification
        to_faculty = Notification.objects.filter(recipient=self.faculty, notification_type='appeal').latest('created_at')
        self.assertEqual(to_faculty.link, '/appeals')

        appeal_id = create.data['id']
        self.login_faculty()
        resolve = self.client.patch(f'/api/exams/{self.exam.id}/appeals/{appeal_id}/',
                                     {'status': 'resolved', 'faculty_response': 'Reviewed, marks unchanged.'}, format='json')
        self.assertEqual(resolve.status_code, 200, resolve.data)
        to_student = Notification.objects.filter(recipient=self.student, notification_type='appeal').latest('created_at')
        self.assertEqual(to_student.link, '/appeals')

    # -- audit log -----------------------------------------------------
    def test_audit_log_is_admin_only_and_paginated(self):
        self.login_faculty()
        self.client.post('/api/question-bank/', {'kind': 'mcq', 'title': 'Q'}, format='json')
        faculty_denied = self.client.get('/api/audit-logs/', {'page_size': 6})
        self.assertEqual(faculty_denied.status_code, 403)
        self.login_admin()
        res = self.client.get('/api/audit-logs/', {'page_size': 6})
        self.assertEqual(res.status_code, 200)
        self.assertIn('page_size', res.data)
        self.assertTrue(any(row['action'] == 'question_bank_created' for row in res.data['logs']))

        self.login_student()
        denied = self.client.get('/api/audit-logs/')
        self.assertEqual(denied.status_code, 403)

    # -- clone exam ------------------------------------------------------
    def test_clone_exam_copies_questions_as_new_draft(self):
        self.login_faculty()
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=2)
        res = self.client.post(f'/api/exams/{self.exam.id}/clone/', {
            'title': 'Cloned Exam', 'start_time': start.isoformat(), 'end_time': end.isoformat(),
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        clone_id = res.data['exam']['id']
        clone = Exam.objects.get(id=clone_id)
        self.assertFalse(clone.is_active)
        self.assertFalse(clone.content_locked)
        self.assertEqual(clone.mcq_questions.count(), self.exam.mcq_questions.count())
        self.assertEqual(clone.coding_problems.count(), self.exam.coding_problems.count())
        # Cloned questions are independent rows, not shared with the source.
        self.assertNotEqual(
            set(clone.mcq_questions.values_list('id', flat=True)),
            set(self.exam.mcq_questions.values_list('id', flat=True)),
        )

    def test_clone_exam_requires_faculty(self):
        self.login_student()
        start = timezone.now() + timedelta(days=1)
        res = self.client.post(f'/api/exams/{self.exam.id}/clone/', {
            'title': 'X', 'start_time': start.isoformat(), 'end_time': (start + timedelta(hours=1)).isoformat(),
        }, format='json')
        self.assertEqual(res.status_code, 403)

    # -- bulk roster import ----------------------------------------------
    def test_roster_import_emails_students_with_an_address(self):
        import io as _io
        from django.core import mail
        csv_body = "enrollment_no,name,email,department\nEN900,New Student,newstudent@test.edu,CSE\n"
        upload = SimpleUploadedFile('roster.csv', csv_body.encode('utf-8'), content_type='text/csv')
        self.login_faculty()
        res = self.client.post(f'/api/exams/{self.exam.id}/roster/import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['created_students'], 1)
        self.assertEqual(res.data['temp_credentials'], [])
        created = User.objects.get(enrollment_no='EN900')
        self.assertFalse(created.has_usable_password())
        self.assertTrue(any('newstudent@test.edu' in m.to for m in mail.outbox))

    def test_roster_import_without_email_returns_usable_temp_password(self):
        """Regression: students imported without an email used to be left
        with an unusable password and no way to ever log in."""
        csv_body = "enrollment_no,name,email,department\nEN901,No Email Student,,CSE\n"
        upload = SimpleUploadedFile('roster.csv', csv_body.encode('utf-8'), content_type='text/csv')
        self.login_faculty()
        res = self.client.post(f'/api/exams/{self.exam.id}/roster/import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['temp_credentials']), 1)
        cred = res.data['temp_credentials'][0]
        self.assertEqual(cred['enrollment_no'], 'EN901')
        created = User.objects.get(enrollment_no='EN901')
        self.assertTrue(created.has_usable_password())
        # The returned temp password is accepted only to create a permanent password.
        self.assertTrue(created.must_change_password)
        self.client.credentials()
        login = self.client.post('/api/auth/student/login/',
                                  {'username': cred['username'], 'password': cred['temp_password']}, format='json')
        self.assertEqual(login.status_code, 403, login.data)
        self.assertTrue(login.data['must_change_password'])
        changed = self.client.post('/api/auth/force-password-change/', {
            'username': cred['username'], 'current_password': cred['temp_password'], 'new_password': 'newpass123'
        }, format='json')
        self.assertEqual(changed.status_code, 200, changed.data)
        login2 = self.client.post('/api/auth/student/login/',
                                   {'username': cred['username'], 'password': 'newpass123'}, format='json')
        self.assertEqual(login2.status_code, 200, login2.data)

    def test_roster_import_requires_faculty(self):
        upload = SimpleUploadedFile('roster.csv', b'enrollment_no,name\nEN902,X\n', content_type='text/csv')
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/roster/import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 403)

    # -- bulk MCQ import ---------------------------------------------------
    def test_bulk_mcq_import_creates_single_and_multi_select_questions(self):
        self.login_faculty()
        self.exam.is_active = False
        self.exam.total_marks = 200
        self.exam.save(update_fields=['is_active', 'total_marks'])
        csv_body = (
            "question_text,option_a,option_b,option_c,option_d,correct_option,marks\n"
            "What is 2+2?,3,4,5,6,B,4\n"
            "Pick the primes,2,3,4,9,\"A,B\",6\n"
        )
        upload = SimpleUploadedFile('mcqs.csv', csv_body.encode('utf-8'), content_type='text/csv')
        res = self.client.post(f'/api/exams/{self.exam.id}/mcqs/bulk-import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['created'], 2)
        self.assertEqual(res.data['errors'], [])
        single = self.exam.mcq_questions.get(question_text='What is 2+2?')
        self.assertEqual(single.question_type, 'single')
        self.assertEqual(single.correct_option, 'B')
        multi = self.exam.mcq_questions.get(question_text='Pick the primes')
        self.assertEqual(multi.question_type, 'multi')
        self.assertEqual(multi.correct_options, ['A', 'B'])

    def test_bulk_mcq_import_reports_bad_rows_without_aborting_good_ones(self):
        self.login_faculty()
        self.exam.is_active = False
        self.exam.total_marks = 200
        self.exam.save(update_fields=['is_active', 'total_marks'])
        csv_body = (
            "question_text,option_a,option_b,option_c,option_d,correct_option,marks\n"
            "Valid question,1,2,3,4,A,4\n"
            "Bad option letter,1,2,3,4,Z,4\n"
            ",1,2,3,4,A,4\n"
        )
        upload = SimpleUploadedFile('mcqs.csv', csv_body.encode('utf-8'), content_type='text/csv')
        res = self.client.post(f'/api/exams/{self.exam.id}/mcqs/bulk-import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['created'], 1)
        self.assertEqual(len(res.data['errors']), 2)
        self.assertTrue(self.exam.mcq_questions.filter(question_text='Valid question').exists())

    def test_bulk_mcq_import_respects_mark_budget(self):
        self.login_faculty()
        self.exam.is_active = False
        self.exam.save(update_fields=['is_active'])  # total_marks stays at the fixture's 100
        csv_body = "question_text,option_a,option_b,option_c,option_d,correct_option,marks\nWay too many marks,1,2,3,4,A,500\n"
        upload = SimpleUploadedFile('mcqs.csv', csv_body.encode('utf-8'), content_type='text/csv')
        res = self.client.post(f'/api/exams/{self.exam.id}/mcqs/bulk-import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['created'], 0)
        self.assertEqual(len(res.data['errors']), 1)

    def test_bulk_mcq_import_blocked_once_exam_is_published(self):
        self.login_faculty()
        csv_body = "question_text,option_a,option_b,option_c,option_d,correct_option,marks\nX,1,2,3,4,A,4\n"
        upload = SimpleUploadedFile('mcqs.csv', csv_body.encode('utf-8'), content_type='text/csv')
        res = self.client.post(f'/api/exams/{self.exam.id}/mcqs/bulk-import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 400)

    def test_bulk_mcq_import_requires_faculty(self):
        upload = SimpleUploadedFile('mcqs.csv', b'question_text,option_a,option_b,option_c,option_d,correct_option\nX,1,2,3,4,A\n', content_type='text/csv')
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/mcqs/bulk-import/', {'file': upload}, format='multipart')
        self.assertEqual(res.status_code, 403)

    # -- appeals -----------------------------------------------------------
    def test_appeal_requires_released_results(self):
        self.login_student()
        StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted', submitted_at=timezone.now())
        res = self.client.post(f'/api/exams/{self.exam.id}/appeals/', {'reason': 'Question was unclear to me.'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_appeal_rejects_short_reason(self):
        self._seed_released_session()
        self.login_student()
        res = self.client.post(f'/api/exams/{self.exam.id}/appeals/', {'reason': 'too short'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_student_cannot_see_other_students_appeals(self):
        self._seed_released_session()
        self._seed_released_session(student=self.student2)
        self.login_student('EN001')
        self.client.post(f'/api/exams/{self.exam.id}/appeals/', {'reason': 'Mine is a valid appeal reason.'}, format='json')
        self.login_student('EN002')
        self.client.post(f'/api/exams/{self.exam.id}/appeals/', {'reason': 'This one belongs to student two.'}, format='json')
        mine = self.client.get(f'/api/exams/{self.exam.id}/appeals/')
        self.assertEqual(len(mine.data['appeals']), 1)

    # -- student progress trend --------------------------------------------
    def test_student_trend_only_includes_released_results(self):
        self._seed_released_session(total_score=72)
        self.login_student()
        res = self.client.get('/api/my-progress/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['trend']), 1)
        self.assertEqual(res.data['trend'][0]['score'], 72)

    # -- question quality ----------------------------------------------------
    def test_question_quality_requires_faculty(self):
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/question-quality/')
        self.assertEqual(res.status_code, 403)

    def test_question_quality_returns_a_row_per_mcq(self):
        StudentExamSession.objects.create(
            exam=self.exam, student=self.student, status='evaluated',
            total_score=90, submitted_at=timezone.now(),
        )
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/question-quality/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['questions']), self.exam.mcq_questions.count())

    # -- result pdf ----------------------------------------------------------
    def test_result_pdf_requires_released_results(self):
        StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted', submitted_at=timezone.now())
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 404)

    def test_result_pdf_downloads_once_released(self):
        self._seed_released_session()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    def _get_pdf_reader(self, res):
        import io
        import pypdf
        content = b''.join(res.streaming_content) if hasattr(res, 'streaming_content') else res.content
        return pypdf.PdfReader(io.BytesIO(content))

    def test_result_pdf_contains_searchable_vector_text(self):
        """Verifies that generated PDF produces selectable, searchable vector text."""
        self._seed_released_session(total_score=85)
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        self.assertGreaterEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn('ACADEMIAPRO', text)
        self.assertIn('EXAMINATION', text)
        self.assertIn('MARKSHEET', text)
        self.assertIn(self.student.name, text)
        self.assertIn('PASS', text)
        self.assertIn('85.00%', text)

    def test_result_pdf_mixed_mcq_and_coding(self):
        """Verifies that an exam with both MCQ and Coding problems generates both component rows."""
        MCQQuestion.objects.create(exam=self.exam, question_text='MCQ Q1', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='A', marks=20.0)
        CodingProblem.objects.create(exam=self.exam, title='Coding P1', marks=30.0, language='python')
        self._seed_released_session(total_score=80)
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        text = reader.pages[0].extract_text()
        self.assertIn('Multiple Choice Questions (MCQ)', text)
        self.assertIn('Programming & Algorithms (Coding)', text)
        self.assertIn('Total Aggregate Performance', text)

    def test_result_pdf_mcq_only(self):
        """Verifies that an MCQ-only exam generates cleanly without Coding rows."""
        mcq_exam = Exam.objects.create(
            title='MCQ Assessment Only', created_by=self.faculty,
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
            duration_minutes=60, passing_marks=20.0, total_marks=50.0,
            results_published=True, results_published_at=timezone.now()
        )
        MCQQuestion.objects.create(exam=mcq_exam, question_text='Q1', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='A', marks=50.0)
        session = StudentExamSession.objects.create(
            exam=mcq_exam, student=self.student, status='evaluated',
            mcq_score=45.0, coding_score=0.0, total_score=45.0, is_passed=True,
            submitted_at=timezone.now(), faculty_verified=True, faculty_verified_at=timezone.now()
        )
        self.login_student()
        res = self.client.get(f'/api/exams/{mcq_exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        text = reader.pages[0].extract_text()
        self.assertIn('Multiple Choice Questions (MCQ)', text)
        self.assertNotIn('Programming & Algorithms (Coding)', text)
        self.assertIn('Total Aggregate Performance', text)

    def test_result_pdf_coding_only(self):
        """Verifies that a Coding-only exam generates cleanly without MCQ rows."""
        code_exam = Exam.objects.create(
            title='Coding Practical Only', created_by=self.faculty,
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
            duration_minutes=60, passing_marks=30.0, total_marks=60.0,
            results_published=True, results_published_at=timezone.now()
        )
        CodingProblem.objects.create(exam=code_exam, title='P1', marks=60.0, language='python')
        session = StudentExamSession.objects.create(
            exam=code_exam, student=self.student, status='evaluated',
            mcq_score=0.0, coding_score=48.0, total_score=48.0, is_passed=True,
            submitted_at=timezone.now(), faculty_verified=True, faculty_verified_at=timezone.now()
        )
        self.login_student()
        res = self.client.get(f'/api/exams/{code_exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        text = reader.pages[0].extract_text()
        self.assertNotIn('Multiple Choice Questions (MCQ)', text)
        self.assertIn('Programming & Algorithms (Coding)', text)
        self.assertIn('Total Aggregate Performance', text)

    def test_result_pdf_fail_status(self):
        """Verifies that a failed session reflects FAIL status and correct marks."""
        session = StudentExamSession.objects.create(
            exam=self.exam, student=self.student, status='evaluated',
            mcq_score=10.0, coding_score=10.0, total_score=20.0, is_passed=False,
            submitted_at=timezone.now(), faculty_verified=True, faculty_verified_at=timezone.now()
        )
        self.close_exam_window()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        text = reader.pages[0].extract_text()
        self.assertIn('FAIL', text)
        self.assertIn('Not Qualified', text)
        self.assertIn('20.00%', text)

    def test_result_pdf_ufm_voided_status(self):
        """Verifies that a voided UFM session displays UNFAIR MEANS and zeroed score."""
        session = StudentExamSession.objects.create(
            exam=self.exam, student=self.student, status='ufm', is_ufm=True,
            ufm_reason='Proctoring violation limits exceeded',
            mcq_score=0.0, coding_score=0.0, total_score=0.0, is_passed=False,
            submitted_at=timezone.now()
        )
        self.close_exam_window()
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        text = reader.pages[0].extract_text()
        self.assertIn('UNFAIR MEANS', text)
        self.assertIn('Attempt Voided', text)
        self.assertIn('0.00%', text)

    def test_result_pdf_long_names_and_titles(self):
        """Verifies that extremely long student names and exam titles render cleanly without errors."""
        long_student = User.objects.create_user(
            username='longname1', password='x',
            name='Hubert Blaine Wolfeschlegelsteinhausenbergerdorff Jr.',
            enrollment_no='EN2026-POLY-999999999',
            department='Interdisciplinary School of Advanced Computational Systems Engineering',
            branch='CE', email='hubert.blaine@university.edu', user_type='student'
        )
        long_exam = Exam.objects.create(
            title='End-Semester Comprehensive Examination in Advanced Heterogeneous Cloud Computing and Microservices',
            subject='Distributed Systems Engineering', phase='T4', created_by=self.faculty,
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
            duration_minutes=120, passing_marks=40.0, total_marks=100.0,
            results_published=True, results_published_at=timezone.now()
        )
        session = StudentExamSession.objects.create(
            exam=long_exam, student=long_student, status='evaluated',
            mcq_score=35.0, coding_score=50.0, total_score=85.0, is_passed=True,
            submitted_at=timezone.now(), faculty_verified=True, faculty_verified_at=timezone.now()
        )
        self.client.credentials()
        self.client.force_authenticate(user=long_student)
        res = self.client.get(f'/api/exams/{long_exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

    def test_result_pdf_graceful_missing_optional_fields(self):
        """Verifies that blank optional fields (department, branch, subject, phase, email) generate without errors."""
        minimal_student = User.objects.create_user(username='minstu', password='x', name='Min Student', user_type='student')
        minimal_exam = Exam.objects.create(
            title='Basic Diagnostic', created_by=self.faculty,
            start_time=timezone.now() - timezone.timedelta(hours=2),
            end_time=timezone.now() - timezone.timedelta(hours=1),
            duration_minutes=60, passing_marks=40.0, total_marks=100.0,
            results_published=True
        )
        session = StudentExamSession.objects.create(
            exam=minimal_exam, student=minimal_student, status='evaluated',
            mcq_score=70.0, coding_score=0.0, total_score=70.0, is_passed=True,
            submitted_at=timezone.now()
        )
        self.client.credentials()
        self.client.force_authenticate(user=minimal_student)
        res = self.client.get(f'/api/exams/{minimal_exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

    def test_result_pdf_no_sensitive_information_leakage(self):
        """Verifies that student source code, proctoring events, and internal secrets are not leaked in PDF."""
        code_p = CodingProblem.objects.create(exam=self.exam, title='Confidential Problem', marks=40.0, language='python')
        session = self._seed_released_session(total_score=88)
        
        # Add submission and proctor event
        secret_code = "def SECRET_SUBMISSION_FUNCTION_12345(): return 'SUPER_SECRET_ALGORITHM'"
        CodingSubmission.objects.create(
            session=session, problem=code_p, submitted_code=secret_code,
            logic_status='correct', marks_awarded=40.0
        )
        ProctorEvent.objects.create(
            session=session, event_type='tab_switch', severity='high',
            details='ip=192.168.1.100 recording_url=https://secret.s3.bucket/video.mp4'
        )
        
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/result-card.pdf')
        self.assertEqual(res.status_code, 200)

        reader = self._get_pdf_reader(res)
        text = reader.pages[0].extract_text()
        self.assertNotIn('SECRET_SUBMISSION_FUNCTION', text)
        self.assertNotIn('SUPER_SECRET_ALGORITHM', text)
        self.assertNotIn('192.168.1.100', text)
        self.assertNotIn('https://secret.s3.bucket', text)
        self.assertNotIn('tab_switch', text)

    # -- calendar export -------------------------------------------------
    def test_calendar_export_requires_exam_access(self):
        """A student with no StudentExamAccess grant for this exam should
        not be able to download its calendar invite."""
        outsider = User.objects.create_user(username='outsider1', password='x', name='Outsider', user_type='student', enrollment_no='EN999')
        self.client.credentials()
        self.client.force_authenticate(user=outsider)
        res = self.client.get(f'/api/exams/{self.exam.id}/calendar.ics')
        self.assertEqual(res.status_code, 403)

    def test_calendar_export_works_for_granted_student_before_exam_starts(self):
        """Unlike the result PDF, the calendar invite must be available
        ahead of time (that's the whole point — planning around it), not
        gated behind results being released."""
        StudentExamAccess.objects.get_or_create(exam=self.exam, student=self.student, defaults={'temp_otp': '000000'})
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/calendar.ics')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/calendar; charset=utf-8')
        body = res.content.decode('utf-8')
        self.assertIn('BEGIN:VEVENT', body)
        self.assertIn('SUMMARY:Test Exam', body)
        self.assertIn('END:VCALENDAR', body)

    def test_calendar_export_available_to_owning_faculty(self):
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/calendar.ics')
        self.assertEqual(res.status_code, 200)

    # -- code similarity / academic integrity ------------------------------
    def test_code_similarity_requires_faculty(self):
        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/')
        self.assertEqual(res.status_code, 403)

    def test_code_similarity_flags_near_identical_submissions(self):
        shared_code = (
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, n in enumerate(nums):\n"
            "        if target - n in seen:\n"
            "            return [seen[target - n], i]\n"
            "        seen[n] = i\n"
        )
        session_a = StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted')
        session_b = StudentExamSession.objects.create(exam=self.exam, student=self.student2, status='submitted')
        CodingSubmission.objects.create(session=session_a, problem=self.problem, language='python', submitted_code=shared_code)
        CodingSubmission.objects.create(session=session_b, problem=self.problem, language='python', submitted_code=shared_code.replace('    ', '  '))

        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['compared_submissions'], 2)
        self.assertEqual(len(res.data['flagged_pairs']), 1)
        pair = res.data['flagged_pairs'][0]
        self.assertGreaterEqual(pair['similarity'], 0.72)
        names = {pair['student_a']['enrollment_no'], pair['student_b']['enrollment_no']}
        self.assertEqual(names, {'EN001', 'EN002'})

    def test_code_similarity_does_not_flag_different_solutions(self):
        session_a = StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted')
        session_b = StudentExamSession.objects.create(exam=self.exam, student=self.student2, status='submitted')
        CodingSubmission.objects.create(
            session=session_a, problem=self.problem, language='python',
            submitted_code="def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i\n",
        )
        CodingSubmission.objects.create(
            session=session_b, problem=self.problem, language='python',
            submitted_code="def two_sum(nums, target):\n    for i in range(len(nums)):\n        for j in range(i + 1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]\n    return []\n",
        )
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['flagged_pairs'], [])

    def test_code_similarity_ignores_cross_language_pairs(self):
        """Same logic in two different languages should never be flagged —
        a textual diff across languages is meaningless."""
        session_a = StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted')
        session_b = StudentExamSession.objects.create(exam=self.exam, student=self.student2, status='submitted')
        CodingSubmission.objects.create(session=session_a, problem=self.problem, language='python', submitted_code="def f(x):\n    return x + 1\n")
        CodingSubmission.objects.create(session=session_b, problem=self.problem, language='java', submitted_code="def f(x):\n    return x + 1\n")
        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['flagged_pairs'], [])

    def test_code_similarity_prunes_impossible_length_pairs(self):
        """Mathematical pruning skips pairs whose upper-bound ratio cannot reach threshold."""
        session_a = StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted')
        session_b = StudentExamSession.objects.create(exam=self.exam, student=self.student2, status='submitted')
        # Very short submission (2 tokens) vs long submission (100 tokens)
        CodingSubmission.objects.create(session=session_a, problem=self.problem, language='python', submitted_code="x = 1\n")
        long_code = "\n".join([f"var_{i} = {i}" for i in range(50)])
        CodingSubmission.objects.create(session=session_b, problem=self.problem, language='python', submitted_code=long_code)

        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/?threshold=0.70')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['compared_submissions'], 2)
        self.assertEqual(res.data['flagged_pairs'], [])

        # With threshold=0.0, the pair is not pruned and is evaluated
        res_zero = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/?threshold=0.0')
        self.assertEqual(res_zero.status_code, 200)
        self.assertEqual(len(res_zero.data['flagged_pairs']), 1)

    def test_code_similarity_c_style_comments_ignored_for_cpp_java_js(self):
        """Comments in C++, Java, and JS must be stripped so comment edits don't change similarity."""
        session_a = StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted')
        session_b = StudentExamSession.objects.create(exam=self.exam, student=self.student2, status='submitted')
        code_a = (
            "// Solution by Student A\n"
            "/* Multi-line algorithm description\n"
            "   Time complexity: O(N) */\n"
            "#include <iostream>\n"
            "int main() {\n"
            "    int a = 10; // set a\n"
            "    std::cout << a;\n"
            "    return 0;\n"
            "}\n"
        )
        code_b = (
            "#include <iostream>\n"
            "int main() {\n"
            "    int a = 10;\n"
            "    std::cout << a;\n"
            "    return 0;\n"
            "}\n"
        )
        CodingSubmission.objects.create(session=session_a, problem=self.problem, language='cpp', submitted_code=code_a)
        CodingSubmission.objects.create(session=session_b, problem=self.problem, language='cpp', submitted_code=code_b)

        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['flagged_pairs']), 1)
        self.assertGreaterEqual(res.data['flagged_pairs'][0]['similarity'], 0.95)

    def test_code_similarity_c_style_strings_and_urls_preserved(self):
        """String literals containing comment-like markers or URLs must not be stripped."""
        from .evaluator import _normalize_tokens
        js_code = 'const endpoint = "http://example.com//api/v1"; const msg = "/* not a comment */";'
        tokens = _normalize_tokens(js_code, 'javascript')
        self.assertEqual(tokens, ['const', 'ID', '=', 'STR', ';', 'const', 'ID', '=', 'STR', ';'])

    def test_code_similarity_audit_log_created_on_success(self):
        """Authorized faculty execution writes a code_similarity_checked audit record."""
        session_a = StudentExamSession.objects.create(exam=self.exam, student=self.student, status='submitted')
        CodingSubmission.objects.create(session=session_a, problem=self.problem, language='python', submitted_code="def f(x):\n    return x\n")

        from .models import AuditLog
        initial_count = AuditLog.objects.filter(action='code_similarity_checked').count()

        self.login_faculty()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/?threshold=0.75')
        self.assertEqual(res.status_code, 200)

        logs = AuditLog.objects.filter(action='code_similarity_checked')
        self.assertEqual(logs.count(), initial_count + 1)
        latest = logs.latest('created_at')
        self.assertEqual(latest.actor, self.faculty)
        self.assertEqual(latest.target_type, 'CodingProblem')
        self.assertEqual(latest.target_id, str(self.problem.id))
        self.assertEqual(latest.details['exam_id'], self.exam.id)
        self.assertEqual(latest.details['threshold'], 0.75)
        self.assertEqual(latest.details['compared_submissions'], 1)

    def test_code_similarity_audit_log_not_created_on_denied_student(self):
        """Denied requests (e.g. from student) do not record a code_similarity_checked audit log."""
        from .models import AuditLog
        initial_count = AuditLog.objects.filter(action='code_similarity_checked').count()

        self.login_student()
        res = self.client.get(f'/api/exams/{self.exam.id}/coding-problems/{self.problem.id}/similarity/')
        self.assertEqual(res.status_code, 403)

        logs = AuditLog.objects.filter(action='code_similarity_checked')
        self.assertEqual(logs.count(), initial_count)

    # -- login throttling scoped per account, not per IP -------------------
    def test_login_throttle_is_scoped_per_account_not_per_ip(self):
        """Regression: a plain IP-keyed login throttle would let one
        student's failed attempts lock out every other student on the same
        network (e.g. a shared campus WiFi/NAT). Repeated bad attempts
        against one account must not affect a different account's ability
        to log in from the same test client / IP."""
        for _ in range(6):
            bad = self.client.post('/api/auth/student/login/', {'username': 'en001', 'password': 'wrong'}, format='json')
            self.assertIn(bad.status_code, (401, 429))
        other = self.client.post('/api/auth/student/login/', {'username': 'en002', 'password': 'x'}, format='json')
        self.assertEqual(other.status_code, 200, other.data)


# =====================================================================
class PracticeModeTests(BaseSetup):
    """Coverage for the self-serve mock test: no camera/mic, no proctoring,
    nothing persisted, faculty-invisible."""

    def setUp(self):
        super().setUp()
        topics = ['Python', 'Python', 'Python', 'Python', 'Python', 'Python', 'Algorithms', 'Algorithms']
        for i, topic in enumerate(topics, 1):
            PracticeQuestion.objects.create(
                topic=topic,
                question_text=f'Practice question {i} in {topic}',
                option_a='Option A',
                option_b='Option B',
                option_c='Option C',
                option_d='Option D',
                correct_option='A',
                explanation=f'Explanation for question {i}',
                is_active=True,
            )

    def test_practice_questions_requires_student(self):
        self.login_faculty()
        res = self.client.get('/api/practice/questions/')
        self.assertEqual(res.status_code, 403)

    def test_practice_questions_returns_requested_count_and_topics(self):
        self.login_student()
        res = self.client.get('/api/practice/questions/', {'count': 5})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['questions']), 5)
        self.assertGreater(len(res.data['topics']), 0)
        # Correct answers are never sent to the client.
        for q in res.data['questions']:
            self.assertIn('options', q)
            self.assertNotIn('correct_option', q)

    def test_practice_questions_filters_by_topic(self):
        self.login_student()
        res = self.client.get('/api/practice/questions/', {'topic': 'Python', 'count': 20})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(q['topic'] == 'Python' for q in res.data['questions']))

    def test_practice_submit_grades_instantly_without_persisting_a_session(self):
        self.login_student()
        fetched = self.client.get('/api/practice/questions/', {'topic': 'Python', 'count': 6}).data['questions']
        from .models import PracticeQuestion
        answers = {}
        for q in fetched:
            answers[str(q['id'])] = PracticeQuestion.objects.get(id=q['id']).correct_option
        res = self.client.post('/api/practice/submit/', {'answers': answers}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], len(fetched))
        self.assertEqual(res.data['percentage'], 100.0)
        # Nothing about a practice attempt is stored anywhere real.
        self.assertEqual(StudentExamSession.objects.filter(student=self.student).count(), 0)

    def test_practice_submit_reports_wrong_answers_with_explanation(self):
        self.login_student()
        fetched = self.client.get('/api/practice/questions/', {'count': 3}).data['questions']
        answers = {str(q['id']): 'Z' for q in fetched}  # guaranteed wrong
        res = self.client.post('/api/practice/submit/', {'answers': answers}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 0)
        self.assertTrue(all(not r['is_correct'] for r in res.data['results']))

    def test_practice_submit_rejects_empty_payload(self):
        self.login_student()
        res = self.client.post('/api/practice/submit/', {'answers': {}}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_practice_submit_requires_student(self):
        self.login_faculty()
        res = self.client.post('/api/practice/submit/', {'answers': {'1': 'A'}}, format='json')
        self.assertEqual(res.status_code, 403)


