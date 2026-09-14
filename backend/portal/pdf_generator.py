"""
AcademiaPro — Modern Academic Exam Result PDF Generator
======================================================
Generates an executive, print-friendly academic marksheet / statement of marks
in standard A4 portrait format (8.27 x 11.69 inches).

Design Standards:
- Corporate/Academic typography hierarchy with slate/navy color palette
- High visual density with zero awkward giant empty whitespace
- Real data only (no fabricated semesters, academic years, or unverified claims)
- Dynamic component breakdown table (MCQ, Coding, Total)
- Performance mastery visualization bar with passing threshold indicator
- Strict privacy guarantees: zero student source code, proctoring events, or internal secrets
- Vector PDF output with 100% searchable and selectable text
"""

import io
import textwrap
from django.utils import timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages


def _format_dt(dt):
    """Safely format datetime object to human-readable string."""
    if not dt:
        return 'N/A'
    try:
        return dt.strftime('%d %b %Y, %H:%M UTC')
    except Exception:
        return str(dt)


def _truncate(text, max_len):
    """Safely truncate text with ellipsis if exceeding max length."""
    if not text:
        return ''
    text = str(text).strip()
    return text if len(text) <= max_len else text[:max_len - 3] + '...'


def generate_exam_result_pdf(session, output_png_path=None):
    """
    Renders a high-fidelity academic result marksheet for a StudentExamSession.

    Args:
        session: StudentExamSession instance (select_related student, exam)
        output_png_path: Optional path to also export a PNG image for visual QA

    Returns:
        io.BytesIO: Buffer containing the generated PDF binary data
    """
    exam = session.exam
    student = session.student

    # ---------------------------------------------------------
    # 1. Extract and Validate Session & Exam Data
    # ---------------------------------------------------------
    raw_name = (student.name or student.username or 'Candidate').strip()
    student_name = _truncate(raw_name, 40)
    enrollment_no = (student.enrollment_no or 'N/A').strip()
    
    # Department & Branch (only real data)
    dept_branch_parts = []
    if student.department:
        dept_branch_parts.append(student.department.strip())
    if student.branch:
        from portal.models import User
        branch_map = dict(getattr(User, 'BRANCH_CHOICES', ()))
        branch_label = branch_map.get(student.branch, student.branch)
        if branch_label and branch_label not in dept_branch_parts:
            dept_branch_parts.append(branch_label)
    
    department_display = ' • '.join(dept_branch_parts) if dept_branch_parts else 'Not Specified'
    department_display = _truncate(department_display, 36)
    student_email = _truncate(student.email or '', 34)

    raw_title = (exam.title or 'Examination Assessment').strip()
    exam_title = _truncate(raw_title, 64)
    
    exam_id_str = f"Exam #{exam.id}"
    phase_display = exam.get_phase_display() if hasattr(exam, 'get_phase_display') and exam.phase else (exam.phase or '')
    if phase_display:
        exam_id_str += f" • Phase {phase_display}"
    
    subject_display = _truncate(exam.subject or '', 34)

    # Scores & Totals (real data)
    total_score = float(session.total_score or 0.0)
    total_max_marks = float(exam.total_marks or 0.0)
    passing_marks = float(exam.passing_marks or 0.0)

    percentage = round((total_score / total_max_marks) * 100, 2) if total_max_marks > 0 else 0.0
    passing_percentage = round((passing_marks / total_max_marks) * 100, 1) if total_max_marks > 0 else 0.0

    # Component data
    mcq_qs = exam.mcq_questions.all()
    mcq_count = mcq_qs.count()
    mcq_max = float(sum(q.marks for q in mcq_qs) if mcq_count > 0 else 0.0)
    mcq_score = float(session.mcq_score or 0.0)
    mcq_pct = round((mcq_score / mcq_max) * 100, 1) if mcq_max > 0 else 0.0

    coding_ps = exam.coding_problems.all()
    coding_count = coding_ps.count()
    coding_max = float(sum(p.marks for p in coding_ps) if coding_count > 0 else 0.0)
    coding_score = float(session.coding_score or 0.0)
    coding_pct = round((coding_score / coding_max) * 100, 1) if coding_max > 0 else 0.0

    total_items = mcq_count + coding_count

    # Result state determination
    is_ufm = bool(session.is_ufm or session.status == 'ufm')
    is_pending = bool(session.status not in ('evaluated', 'submitted', 'ufm') or (session.status == 'submitted' and not exam.results_published))
    is_passed = bool(session.is_passed)

    if is_ufm:
        status_badge_text = 'UNFAIR MEANS'
        status_sub_text = 'Attempt Voided'
        badge_fg = '#991B1B'       # Dark crimson
        badge_bg = '#FEE2E2'       # Light crimson fill
        badge_border = '#FCA5A5'   # Crimson border
        gauge_color = '#DC2626'
        result_statement = 'The examination attempt was voided due to unfair means / proctoring violations recorded during the session.'
    elif is_pending:
        status_badge_text = 'PENDING'
        status_sub_text = 'Under Evaluation'
        badge_fg = '#4338CA'       # Indigo
        badge_bg = '#EEF2FF'
        badge_border = '#C7D2FE'
        gauge_color = '#6366F1'
        result_statement = 'The examination submission is currently pending final evaluation.'
    elif is_passed:
        status_badge_text = 'PASS'
        status_sub_text = 'Qualified'
        badge_fg = '#047857'       # Emerald green
        badge_bg = '#ECFDF5'
        badge_border = '#A7F3D0'
        gauge_color = '#10B981' if percentage >= 70 else '#3B82F6'
        result_statement = 'The candidate has successfully met the academic criteria and achieved the required passing standard.'
    else:
        status_badge_text = 'FAIL'
        status_sub_text = 'Not Qualified'
        badge_fg = '#B91C1C'       # Red
        badge_bg = '#FEF2F2'
        badge_border = '#FECACA'
        gauge_color = '#EF4444'
        result_statement = 'The candidate did not meet the minimum aggregate passing standard established for this examination.'

    doc_ref = f"AP-RES-{exam.id:04d}-{session.id:05d}"
    now_dt = timezone.now()
    issue_date_str = _format_dt(now_dt)

    # ---------------------------------------------------------
    # 2. Setup A4 Page Canvas (8.27 x 11.69 inches)
    # ---------------------------------------------------------
    fig = plt.figure(figsize=(8.27, 11.69), dpi=300)
    fig.patch.set_facecolor('#FFFFFF')
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Color Palette
    C_NAVY_DARK = '#0F172A'    # slate-900
    C_NAVY_MED = '#1E293B'     # slate-800
    C_BODY = '#334155'         # slate-700
    C_MUTED = '#64748B'        # slate-500
    C_LIGHT_BG = '#F8FAFC'     # slate-50
    C_BORDER = '#E2E8F0'       # slate-200
    C_ACCENT_BLUE = '#2563EB'  # blue-600

    # Top Brand Ribbon
    ax.add_patch(patches.Rectangle((0, 0.993), 1.0, 0.007, facecolor=C_ACCENT_BLUE, edgecolor='none'))

    # ---------------------------------------------------------
    # 3. Header Section (y: 0.965 -> 0.890)
    # ---------------------------------------------------------
    ax.text(0.07, 0.958, 'ACADEMIAPRO', fontsize=17, fontweight='bold', color=C_NAVY_DARK, va='top')
    ax.text(0.07, 0.932, 'Digital Examination & Assessment Platform', fontsize=8.5, color=C_MUTED, va='top')
    ax.text(0.07, 0.915, 'Central Academic Evaluation Division', fontsize=7.5, color='#94A3B8', va='top')

    ax.text(0.93, 0.958, 'EXAMINATION RESULT MARKSHEET', fontsize=12, fontweight='bold', color=C_NAVY_MED, ha='right', va='top')
    ax.text(0.93, 0.936, 'Official Statement of Marks & Evaluation', fontsize=8.5, color=C_MUTED, ha='right', va='top')
    ax.text(0.93, 0.916, f'DOC REF: {doc_ref}', fontsize=8, fontweight='bold', fontfamily='monospace', color=C_BODY, ha='right', va='top')

    ax.plot([0.07, 0.93], [0.895, 0.895], color=C_BORDER, linewidth=1.0)

    # ---------------------------------------------------------
    # 4. Student & Assessment Info Card (y: 0.875 -> 0.720)
    # ---------------------------------------------------------
    card_y = 0.720
    card_h = 0.155
    card_box = patches.FancyBboxPatch(
        (0.07, card_y), 0.86, card_h,
        boxstyle="round,pad=0.012,rounding_size=0.010",
        facecolor=C_LIGHT_BG, edgecolor=C_BORDER, linewidth=1.0
    )
    ax.add_patch(card_box)

    # Card Title Bar
    ax.text(0.09, 0.860, 'CANDIDATE & EXAMINATION PROFILE', fontsize=8, fontweight='bold', color=C_MUTED, va='center')
    ax.plot([0.09, 0.91], [0.848, 0.848], color=C_BORDER, linewidth=0.75)

    # Vertical Column Separator
    ax.plot([0.50, 0.50], [0.730, 0.838], color=C_BORDER, linewidth=0.75)

    # Left Column: Candidate Details (Fixed non-colliding slots)
    ax.text(0.09, 0.834, 'Candidate Name', fontsize=7, fontweight='bold', color=C_MUTED, va='top')
    ax.text(0.09, 0.820, student_name, fontsize=9.5, fontweight='bold', color=C_NAVY_DARK, va='top')
    ax.text(0.09, 0.795, f'Enrollment No: {enrollment_no}', fontsize=8, fontweight='bold', color=C_BODY, va='top')
    
    if department_display != 'Not Specified':
        ax.text(0.09, 0.772, f'Dept: {department_display}', fontsize=7.5, color=C_BODY, va='top')
    else:
        ax.text(0.09, 0.772, 'Dept: Not Specified', fontsize=7.5, color=C_MUTED, va='top')
        
    if student_email:
        ax.text(0.09, 0.750, f'Email: {student_email}', fontsize=7.5, color=C_MUTED, va='top')

    # Right Column: Examination Details (Fixed non-colliding slots)
    ax.text(0.52, 0.834, 'Assessment Title', fontsize=7, fontweight='bold', color=C_MUTED, va='top')
    wrapped_exam = textwrap.fill(exam_title, width=34)
    ax.text(0.52, 0.820, wrapped_exam, fontsize=8.5, fontweight='bold', color=C_NAVY_DARK, va='top')

    ax.text(0.52, 0.780, f'{exam_id_str}', fontsize=8, fontweight='bold', color=C_BODY, va='top')
    
    if subject_display:
        ax.text(0.52, 0.758, f'Subject: {subject_display}', fontsize=7.5, color=C_BODY, va='top')
    
    session_timing_str = _format_dt(session.submitted_at or session.started_at)
    ax.text(0.52, 0.736, f'Submitted: {session_timing_str}', fontsize=7.5, color=C_MUTED, va='top')

    # ---------------------------------------------------------
    # 5. Result Summary & Score Hero Section (y: 0.700 -> 0.565)
    # ---------------------------------------------------------
    hero_y = 0.565
    hero_h = 0.135
    hero_box = patches.FancyBboxPatch(
        (0.07, hero_y), 0.86, hero_h,
        boxstyle="round,pad=0.012,rounding_size=0.010",
        facecolor='#FFFFFF', edgecolor='#CBD5E1', linewidth=1.2
    )
    ax.add_patch(hero_box)

    # Col 1: Total Obtained Marks
    ax.text(0.10, 0.672, 'TOTAL MARKS OBTAINED', fontsize=7.5, fontweight='bold', color=C_MUTED, va='top')
    score_display = f"{total_score:g}" if not is_ufm else "0.0 (Voided)"
    ax.text(0.10, 0.648, score_display, fontsize=22, fontweight='bold', color=C_NAVY_DARK, va='top')
    ax.text(0.10, 0.590, f'Out of {total_max_marks:g} Maximum Marks', fontsize=8, color=C_MUTED, va='top')

    # Hero Col 1-2 Separator
    ax.plot([0.37, 0.37], [0.580, 0.675], color=C_BORDER, linewidth=0.8)

    # Col 2: Overall Percentage
    ax.text(0.40, 0.672, 'OVERALL PERCENTAGE', fontsize=7.5, fontweight='bold', color=C_MUTED, va='top')
    pct_display = f"{percentage:.2f}%" if not is_ufm else "0.00%"
    pct_color = C_ACCENT_BLUE if is_passed else (C_MUTED if is_pending else '#DC2626')
    ax.text(0.40, 0.648, pct_display, fontsize=22, fontweight='bold', color=pct_color, va='top')
    pass_std_text = f'Passing Standard: {passing_marks:g} Marks ({passing_percentage:.1f}%)' if passing_marks > 0 else 'Passing Standard: Complete'
    ax.text(0.40, 0.590, pass_std_text, fontsize=8, color=C_MUTED, va='top')

    # Hero Col 2-3 Separator
    ax.plot([0.67, 0.67], [0.580, 0.675], color=C_BORDER, linewidth=0.8)

    # Col 3: Final Status Badge
    ax.text(0.70, 0.672, 'FINAL RESULT STATUS', fontsize=7.5, fontweight='bold', color=C_MUTED, va='top')
    
    # Rounded Status Pill
    pill_patch = patches.FancyBboxPatch(
        (0.70, 0.612), 0.20, 0.040,
        boxstyle="round,pad=0.008,rounding_size=0.010",
        facecolor=badge_bg, edgecolor=badge_border, linewidth=1.2
    )
    ax.add_patch(pill_patch)
    ax.text(0.80, 0.632, status_badge_text, fontsize=12, fontweight='bold', color=badge_fg, ha='center', va='center')
    ax.text(0.80, 0.590, status_sub_text, fontsize=7.5, fontweight='bold', color=badge_fg, ha='center', va='top')

    # ---------------------------------------------------------
    # 6. Component Performance Table (y: 0.540 -> 0.380)
    # ---------------------------------------------------------
    table_top = 0.535
    ax.text(0.07, table_top, 'COMPONENT PERFORMANCE BREAKDOWN', fontsize=8.5, fontweight='bold', color=C_NAVY_DARK, va='top')

    th_y = table_top - 0.020
    th_h = 0.024
    header_rect = patches.Rectangle((0.07, th_y - th_h), 0.86, th_h, facecolor=C_NAVY_DARK, edgecolor='none')
    ax.add_patch(header_rect)

    # Column Titles
    ax.text(0.09, th_y - 0.012, 'Assessment Component', fontsize=7.5, fontweight='bold', color='#FFFFFF', va='center')
    ax.text(0.42, th_y - 0.012, 'Items', fontsize=7.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')
    ax.text(0.55, th_y - 0.012, 'Max Marks', fontsize=7.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')
    ax.text(0.68, th_y - 0.012, 'Marks Awarded', fontsize=7.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')
    ax.text(0.81, th_y - 0.012, 'Percentage', fontsize=7.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')
    ax.text(0.90, th_y - 0.012, 'Status', fontsize=7.5, fontweight='bold', color='#FFFFFF', ha='center', va='center')

    # Table Rows
    rows = []
    if mcq_count > 0:
        mcq_status = 'PASS' if (mcq_score >= (mcq_max * 0.4)) else 'ATTEMPTED'
        if is_ufm: mcq_status = 'VOIDED'
        rows.append({
            'name': 'Multiple Choice Questions (MCQ)',
            'items': f'{mcq_count} Qs',
            'max': f'{mcq_max:g}',
            'awarded': f'{mcq_score:g}' if not is_ufm else '0.0',
            'pct': f'{mcq_pct:.1f}%' if not is_ufm else '0.0%',
            'status': mcq_status,
            'is_total': False
        })
    if coding_count > 0:
        coding_status = 'PASS' if (coding_score >= (coding_max * 0.4)) else 'EVALUATED'
        if is_ufm: coding_status = 'VOIDED'
        rows.append({
            'name': 'Programming & Algorithms (Coding)',
            'items': f'{coding_count} Problems',
            'max': f'{coding_max:g}',
            'awarded': f'{coding_score:g}' if not is_ufm else '0.0',
            'pct': f'{coding_pct:.1f}%' if not is_ufm else '0.0%',
            'status': coding_status,
            'is_total': False
        })

    # Total Aggregate Row
    rows.append({
        'name': 'Total Aggregate Performance',
        'items': f'{total_items} Total Items',
        'max': f'{total_max_marks:g}',
        'awarded': f'{total_score:g}' if not is_ufm else '0.0',
        'pct': f'{percentage:.2f}%' if not is_ufm else '0.0%',
        'status': status_badge_text,
        'is_total': True
    })

    current_y = th_y - th_h
    row_h = 0.026

    for idx, row in enumerate(rows):
        row_y = current_y - row_h
        if row['is_total']:
            row_bg = '#F1F5F9'
            ax.add_patch(patches.Rectangle((0.07, row_y), 0.86, row_h, facecolor=row_bg, edgecolor='none'))
            ax.plot([0.07, 0.93], [current_y, current_y], color=C_NAVY_MED, linewidth=1.2)
            ax.plot([0.07, 0.93], [row_y, row_y], color=C_NAVY_MED, linewidth=1.2)
            font_w = 'bold'
            txt_c = C_NAVY_DARK
        else:
            row_bg = '#FFFFFF' if (idx % 2 == 0) else '#F8FAFC'
            ax.add_patch(patches.Rectangle((0.07, row_y), 0.86, row_h, facecolor=row_bg, edgecolor='none'))
            ax.plot([0.07, 0.93], [row_y, row_y], color=C_BORDER, linewidth=0.6)
            font_w = 'normal'
            txt_c = C_BODY

        ax.text(0.09, row_y + (row_h / 2), row['name'], fontsize=8, fontweight=font_w, color=txt_c, va='center')
        ax.text(0.42, row_y + (row_h / 2), row['items'], fontsize=8, fontweight=font_w, color=C_MUTED, ha='center', va='center')
        ax.text(0.55, row_y + (row_h / 2), row['max'], fontsize=8, fontweight=font_w, color=txt_c, ha='center', va='center')
        ax.text(0.68, row_y + (row_h / 2), row['awarded'], fontsize=8, fontweight=font_w, color=txt_c, ha='center', va='center')
        ax.text(0.81, row_y + (row_h / 2), row['pct'], fontsize=8, fontweight=font_w, color=txt_c, ha='center', va='center')
        
        status_c = badge_fg if row['is_total'] else C_BODY
        ax.text(0.90, row_y + (row_h / 2), row['status'], fontsize=7.5, fontweight='bold', color=status_c, ha='center', va='center')

        current_y = row_y

    table_bottom = current_y
    ax.plot([0.07, 0.07], [th_y, table_bottom], color=C_BORDER, linewidth=1.0)
    ax.plot([0.93, 0.93], [th_y, table_bottom], color=C_BORDER, linewidth=1.0)

    # ---------------------------------------------------------
    # 7. Performance Visualization Gauge (y: 0.360 -> 0.280)
    # ---------------------------------------------------------
    gauge_top = table_bottom - 0.025
    ax.text(0.07, gauge_top, 'OVERALL PERFORMANCE MASTERY SCALE', fontsize=8, fontweight='bold', color=C_NAVY_DARK, va='top')
    if 0 < passing_percentage < 100:
        ax.text(0.93, gauge_top, f'Passing Standard: {passing_percentage:.1f}% ({passing_marks:g} Marks)', fontsize=7.5, fontweight='bold', color=C_NAVY_MED, ha='right', va='top')

    track_y = gauge_top - 0.022
    track_h = 0.012
    track_x = 0.09
    track_w = 0.82

    # Background Track
    ax.add_patch(patches.FancyBboxPatch(
        (track_x, track_y), track_w, track_h,
        boxstyle="round,pad=0.002,rounding_size=0.005",
        facecolor='#E2E8F0', edgecolor='none'
    ))

    # Filled Performance Bar
    effective_pct = 0.0 if is_ufm else min(max(percentage, 0.0), 100.0)
    if effective_pct > 0:
        fill_w = max(track_w * (effective_pct / 100.0), 0.01)
        ax.add_patch(patches.FancyBboxPatch(
            (track_x, track_y), fill_w, track_h,
            boxstyle="round,pad=0.002,rounding_size=0.005",
            facecolor=gauge_color, edgecolor='none'
        ))

    # Passing Threshold Marker
    if 0 < passing_percentage < 100:
        thresh_x = track_x + (track_w * (passing_percentage / 100.0))
        ax.plot([thresh_x, thresh_x], [track_y - 0.004, track_y + track_h + 0.004], color=C_NAVY_DARK, linewidth=1.5, linestyle='--')

    # Gauge Scale Labels
    ax.text(track_x, track_y - 0.007, '0%', fontsize=7, color=C_MUTED, ha='left', va='top')
    ax.text(track_x + (track_w * 0.25), track_y - 0.007, '25%', fontsize=7, color='#94A3B8', ha='center', va='top')
    ax.text(track_x + (track_w * 0.50), track_y - 0.007, '50%', fontsize=7, color='#94A3B8', ha='center', va='top')
    ax.text(track_x + (track_w * 0.75), track_y - 0.007, '75%', fontsize=7, color='#94A3B8', ha='center', va='top')
    ax.text(track_x + track_w, track_y - 0.007, '100%', fontsize=7, color=C_MUTED, ha='right', va='top')

    # ---------------------------------------------------------
    # 8. Result Statement & Verification Box (y: 0.255 -> 0.095)
    # ---------------------------------------------------------
    stmt_y = 0.095
    stmt_h = 0.155
    stmt_box = patches.FancyBboxPatch(
        (0.07, stmt_y), 0.86, stmt_h,
        boxstyle="round,pad=0.012,rounding_size=0.010",
        facecolor=C_LIGHT_BG, edgecolor=C_BORDER, linewidth=1.0
    )
    ax.add_patch(stmt_box)

    ax.text(0.09, stmt_y + stmt_h - 0.016, 'OFFICIAL STATEMENT & VERIFICATION RECORD', fontsize=8, fontweight='bold', color=C_MUTED, va='top')
    ax.plot([0.09, 0.91], [stmt_y + stmt_h - 0.022, stmt_y + stmt_h - 0.022], color=C_BORDER, linewidth=0.75)

    wrapped_stmt = textwrap.fill(f"Result Statement: {result_statement}", width=88)
    ax.text(0.09, stmt_y + stmt_h - 0.032, wrapped_stmt, fontsize=7.5, color=C_NAVY_DARK, va='top')

    y_ver_cursor = stmt_y + stmt_h - 0.060
    if session.faculty_verified:
        verifier_name = session.faculty_verified_by.name if session.faculty_verified_by else 'Faculty Examiner'
        ver_date = _format_dt(session.faculty_verified_at)
        ver_text = f"Faculty Verification: Certified by {verifier_name} on {ver_date}."
    else:
        ver_text = "Faculty Verification: Automated central evaluation recorded; formal verification logged."
    ax.text(0.09, y_ver_cursor, ver_text, fontsize=7.5, fontweight='bold', color=C_BODY, va='top')

    y_ver_cursor -= 0.020
    pub_date = _format_dt(exam.results_published_at or exam.end_time)
    pub_text = f"Result Publication: Released via AcademiaPro Examination Engine on {pub_date}."
    ax.text(0.09, y_ver_cursor, pub_text, fontsize=7.5, color=C_BODY, va='top')

    y_ver_cursor -= 0.020
    auth_notice = "Authenticity Notice: This electronically generated statement is authenticated by AcademiaPro digital records. Any unauthorized alteration renders this document void."
    ax.text(0.09, y_ver_cursor, auth_notice, fontsize=7, color='#94A3B8', style='italic', va='top')

    # ---------------------------------------------------------
    # 9. Document Footer (y: 0.055 -> 0.025)
    # ---------------------------------------------------------
    ax.plot([0.07, 0.93], [0.055, 0.055], color=C_BORDER, linewidth=0.8)
    ax.text(0.07, 0.036, 'AcademiaPro Digital Examination Platform • Confidential Academic Record', fontsize=7, color='#94A3B8', va='top')
    ax.text(0.93, 0.036, f'Page 1 of 1 • Ref: {doc_ref}', fontsize=7, color='#94A3B8', ha='right', va='top')

    # ---------------------------------------------------------
    # 10. Save to Vector PDF Stream
    # ---------------------------------------------------------
    pdf_stream = io.BytesIO()
    with PdfPages(pdf_stream) as pdf:
        pdf.savefig(fig, bbox_inches='tight', pad_inches=0.1, dpi=300)

    if output_png_path:
        fig.savefig(output_png_path, bbox_inches='tight', pad_inches=0.1, dpi=200)

    plt.close(fig)
    pdf_stream.seek(0)
    return pdf_stream
