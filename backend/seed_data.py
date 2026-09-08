import os
import sys
import django
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_portal.settings')
django.setup()

from portal.models import (User, Exam, StudentExamAccess, MCQQuestion, CodingProblem,
                           ReferenceSolution, CodingTestCase, FacultyNote, StudentNote)

def seed():
    print("Seeding database...")
    # 1. Create Faculty
    faculty, _ = User.objects.get_or_create(
        username='prof_sharma',
        defaults={
            'email': 'sharma@cs.univ.edu',
            'name': 'Prof. Rajesh Sharma',
            'user_type': 'faculty',
            'department': 'Computer Science & Engineering'
        }
    )
    faculty.set_password('faculty123')
    faculty.save()
    print("Created Faculty: username=prof_sharma / password=faculty123")

    admin_user, _ = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@academiapro.local',
            'name': 'System Admin',
            'user_type': 'admin',
            'department': 'Administration',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    admin_user.user_type = 'admin'
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.set_password('admin123')
    admin_user.save()
    print("Created Admin: username=admin / password=admin123")

    # 2. Create Students
    students_data = [
        ('EN2026001', 'Aarav Patel', 'aarav@student.univ.edu'),
        ('EN2026002', 'Riya Desai', 'riya@student.univ.edu'),
        ('EN2026003', 'Vikram Mehta', 'vikram@student.univ.edu'),
        ('EN2026004', 'Ananya Joshi', 'ananya@student.univ.edu'),
        ('EN2026005', 'Kabir Singh', 'kabir@student.univ.edu'),
    ]
    students = []
    for en_no, name, email in students_data:
        student, _ = User.objects.get_or_create(
            enrollment_no=en_no,
            defaults={
                'username': en_no.lower(),
                'name': name,
                'email': email,
                'user_type': 'student',
                'department': 'Computer Science & Engineering'
            }
        )
        student.set_password('student123')
        student.save()
        students.append(student)
    print(f"Created {len(students)} Students: e.g. Enrollment: EN2026001")

    # 3. Create Sample Exam
    now = timezone.now()
    exam, created = Exam.objects.get_or_create(
        title="Mid-Semester Algorithms & Data Structures Exam",
        defaults={
            'description': "Comprehensive evaluation covering Array manipulation, Time Complexity, and Algorithm Logic.",
            'subject': "Data Structures",
            'phase': "T2",
            'created_by': faculty,
            'start_time': now - timedelta(minutes=15),
            'end_time': now + timedelta(hours=4),
            'duration_minutes': 90,
            'passing_marks': 35.0,
            'total_marks': 84.0,
            'is_active': True,
            'requires_otp': True
        }
    )
    if not created:
        exam.start_time = now - timedelta(minutes=15)
        exam.end_time = now + timedelta(hours=4)
        exam.is_active = True
        if not exam.subject:
            exam.subject = "Data Structures"
        if not exam.phase:
            exam.phase = "T2"
        exam.save()
    print(f"Created/Updated Exam: {exam.title}")

    # 4. Generate Temporary OTPs
    otps = {
        'EN2026001': '482910',
        'EN2026002': '819234',
        'EN2026003': '391029',
        'EN2026004': '654321',
        'EN2026005': '205817'
    }
    for student in students:
        access, _ = StudentExamAccess.objects.get_or_create(exam=exam, student=student)
        access.temp_otp = otps.get(student.enrollment_no, '123456')
        access.is_active = True
        access.cleared_at = None
        access.save()
    print("Assigned temporary OTPs to students:")
    for en_no, otp in otps.items():
        print(f"  -> Enrollment: {en_no} | Temporary OTP: {otp}")

    # 5. Create MCQs
    if exam.mcq_questions.count() == 0:
        mcqs_list = [
            {
                'question_text': 'What is the worst-case time complexity of QuickSort when picking the first element as pivot on an already sorted array?',
                'a': 'O(N)', 'b': 'O(N log N)', 'c': 'O(N^2)', 'd': 'O(log N)',
                'correct': 'C', 'marks': 4.0
            },
            {
                'question_text': 'Which data structure is most suitable for implementing Breadth-First Search (BFS) on a graph?',
                'a': 'Stack', 'b': 'Queue', 'c': 'Priority Queue', 'd': 'Hash Table',
                'correct': 'B', 'marks': 4.0
            },
            {
                'question_text': 'In binary search, how many maximum comparisons are needed to find an element in a sorted array of 1024 items?',
                'a': '10', 'b': '11', 'c': '512', 'd': '1024',
                'correct': 'B', 'marks': 4.0
            },
            {
                'question_text': 'Which collision resolution technique in hash tables uses a linked list at each bucket index?',
                'a': 'Linear Probing', 'b': 'Quadratic Probing', 'c': 'Separate Chaining', 'd': 'Double Hashing',
                'correct': 'C', 'marks': 4.0
            },
            {
                'question_text': 'What is the space complexity of Depth First Search (DFS) on a binary tree of height H?',
                'a': 'O(1)', 'b': 'O(H)', 'c': 'O(2^H)', 'd': 'O(N log N)',
                'correct': 'B', 'marks': 4.0
            },
            {
                'question_text': 'Which of the following sorting algorithms have a worst-case time complexity of O(N log N)? (Select all that apply)',
                'a': 'Merge Sort', 'b': 'Heap Sort', 'c': 'Quick Sort (naive pivot)', 'd': 'Bubble Sort',
                'question_type': 'multi', 'correct_options': ['A', 'B'], 'marks': 4.0
            }
        ]
        for item in mcqs_list:
            MCQQuestion.objects.create(
                exam=exam,
                question_text=item['question_text'],
                option_a=item['a'], option_b=item['b'], option_c=item['c'], option_d=item['d'],
                question_type=item.get('question_type', 'single'),
                correct_option=item.get('correct', ''),
                correct_options=item.get('correct_options', []),
                marks=item['marks']
            )
        print("Created 6 MCQ Questions (including 1 multi-select).")

    # 6. Create Coding Problems & Reference Solutions
    if exam.coding_problems.count() == 0:
        # Coding Problem 1
        cp1 = CodingProblem.objects.create(
            exam=exam,
            title="Two Sum Problem (Indices of Target)",
            problem_statement="Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\nReturn the answer as a pair or list of two indices.",
            input_format="First line contains space-separated integers representing array elements.\nSecond line contains the integer target.",
            output_format="Two space-separated indices sorted in ascending order.",
            sample_input="2 7 11 15\n9",
            sample_output="0 1",
            marks=30.0,
            language="python"
        )
        CodingTestCase.objects.create(problem=cp1, input_data="2 7 11 15\n9", expected_output="0 1", is_hidden=False)
        CodingTestCase.objects.create(problem=cp1, input_data="3 2 4\n6", expected_output="1 2", is_hidden=True)

        ReferenceSolution.objects.create(
            problem=cp1,
            title="Solution 1: Optimal Hash Map One-Pass Approach O(N)",
            language="python",
            code="""def two_sum(nums, target):
    num_to_index = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in num_to_index:
            return [num_to_index[complement], i]
        num_to_index[num] = i
    return []

# Read input
import sys
input_data = sys.stdin.read().splitlines()
if input_data:
    nums = list(map(int, input_data[0].split()))
    target = int(input_data[1])
    res = sorted(two_sum(nums, target))
    print(res[0], res[1])""",
            logic_explanation="Instead of using two nested loops which takes O(N^2) time, we iterate through the array once and store each number along with its index in a hash map (dictionary). For each element `num`, we check if `target - num` already exists in our hash map. If it does, we found our pair in O(1) lookup time, resulting in overall O(N) time and O(N) space complexity."
        )

        ReferenceSolution.objects.create(
            problem=cp1,
            title="Solution 2: Two Pointers Sorting Approach O(N log N)",
            language="python",
            code="""def two_sum_two_pointers(nums, target):
    indexed_nums = [(num, idx) for idx, num in enumerate(nums)]
    indexed_nums.sort()
    left, right = 0, len(nums) - 1
    while left < right:
        curr_sum = indexed_nums[left][0] + indexed_nums[right][0]
        if curr_sum == target:
            return [indexed_nums[left][1], indexed_nums[right][1]]
        elif curr_sum < target:
            left += 1
        else:
            right -= 1
    return []""",
            logic_explanation="We pair each element with its original index, then sort the array. Using two pointers (one at the start and one at the end), we check the sum. If the sum is smaller than target, we increment the left pointer; if larger, we decrement the right pointer. Time complexity is dominated by sorting at O(N log N)."
        )

        ReferenceSolution.objects.create(
            problem=cp1,
            title="Solution 3: Brute Force Approach O(N^2)",
            language="python",
            code="""def two_sum_brute(nums, target):
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []""",
            logic_explanation="The simplest brute force logic checks every possible pair (i, j) where i < j to see if their sum equals the target. While easy to write, this takes O(N^2) time and O(1) space."
        )

        # Coding Problem 2
        cp2 = CodingProblem.objects.create(
            exam=exam,
            title="Longest Substring Without Repeating Characters",
            problem_statement="Given a string `s`, find the length of the longest substring without repeating characters.\nFor example, given `abcabcbb`, the answer is `abc`, which has length 3.",
            input_format="A single string s on the first line.",
            output_format="An integer representing the maximum length.",
            sample_input="abcabcbb",
            sample_output="3",
            marks=30.0,
            language="python"
        )
        CodingTestCase.objects.create(problem=cp2, input_data="abcabcbb", expected_output="3", is_hidden=False)
        CodingTestCase.objects.create(problem=cp2, input_data="bbbbb", expected_output="1", is_hidden=True)

        ReferenceSolution.objects.create(
            problem=cp2,
            title="Solution 1: Sliding Window Optimized with Character Index Map O(N)",
            language="python",
            code="""def length_of_longest_substring(s: str) -> int:
    char_map = {}
    left = 0
    max_length = 0
    for right, char in enumerate(s):
        if char in char_map and char_map[char] >= left:
            left = char_map[char] + 1
        char_map[char] = right
        max_length = max(max_length, right - left + 1)
    return max_length

import sys
s = sys.stdin.read().strip()
print(length_of_longest_substring(s))""",
            logic_explanation="We maintain a sliding window `[left, right]` where all characters inside are unique. When we encounter a character that we have seen previously and its previous index is within the window (`>= left`), we immediately jump our `left` pointer just past the previous occurrence. This guarantees O(N) time complexity as each character is processed at most twice."
        )

        ReferenceSolution.objects.create(
            problem=cp2,
            title="Solution 2: Sliding Window using Hash Set O(2N)",
            language="python",
            code="""def length_of_longest_substring_set(s: str) -> int:
    char_set = set()
    left = 0
    max_len = 0
    for right in range(len(s)):
        while s[right] in char_set:
            char_set.remove(s[left])
            left += 1
        char_set.add(s[right])
        max_len = max(max_len, right - left + 1)
    return max_len""",
            logic_explanation="Using a Hash Set to track unique characters in the current window. When a duplicate is found at `right`, we increment `left` and remove characters from the set until the duplicate is gone."
        )

        print("Created 2 Coding Problems with 2-3 reference solutions each.")

    # ------------------------------------------------------------------
    # 7. Faculty Notes (study material shared with students)
    # ------------------------------------------------------------------
    notes_data = [
        {
            'title': 'Time Complexity & Big-O Notation — Complete Guide',
            'subject': 'Algorithms',
            'description': 'Master sheet covering asymptotic analysis, common complexity classes and how to derive them.',
            'is_pinned': True,
            'content': (
                "1. WHAT IS BIG-O?\n"
                "Big-O describes the upper bound on the growth rate of an algorithm's running time "
                "as the input size n grows.\n\n"
                "2. COMMON CLASSES (best -> worst)\n"
                "   O(1)        constant      - array index access, hash lookup\n"
                "   O(log n)    logarithmic   - binary search, balanced BST operations\n"
                "   O(n)        linear        - single pass over an array\n"
                "   O(n log n)  linearithmic  - merge sort, heap sort, Python's sorted()\n"
                "   O(n^2)      quadratic     - nested loops, bubble/insertion sort\n"
                "   O(2^n)      exponential   - naive recursive subsets / fibonacci\n"
                "   O(n!)       factorial     - brute-force permutations (TSP)\n\n"
                "3. RULES FOR DERIVING COMPLEXITY\n"
                "   a) Drop constants:  O(2n) -> O(n)\n"
                "   b) Drop lower order terms: O(n^2 + n) -> O(n^2)\n"
                "   c) Sequential blocks add: O(a) + O(b)\n"
                "   d) Nested loops multiply: O(a * b)\n\n"
                "4. SPACE COMPLEXITY\n"
                "Count auxiliary memory only. Recursion consumes O(depth) stack space — "
                "a recursive DFS on a skewed tree of n nodes is O(n) space.\n\n"
                "5. EXAM TIP\n"
                "When asked to 'optimise', the usual jump is O(n^2) -> O(n) by trading time for "
                "space with a hash map, or O(n^2) -> O(n log n) by sorting first."
            ),
            'visibility': 'all',
        },
        {
            'title': 'Hash Maps & The Two-Sum Pattern',
            'subject': 'Data Structures',
            'description': 'Why a dictionary turns most "find the pair/triplet" problems from quadratic into linear.',
            'content': (
                "THE CORE IDEA\n"
                "A hash map gives you average O(1) insert and lookup. Any time a brute-force solution "
                "re-scans the array to answer 'have I seen X before?', a hash map removes the inner loop.\n\n"
                "TEMPLATE\n"
                "    seen = {}\n"
                "    for i, value in enumerate(nums):\n"
                "        complement = target - value\n"
                "        if complement in seen:\n"
                "            return [seen[complement], i]\n"
                "        seen[value] = i\n\n"
                "WHY IT WORKS\n"
                "We only ever look *backwards* at elements already stored, so each pair is considered "
                "exactly once and no element is matched with itself.\n\n"
                "RELATED PROBLEMS\n"
                "  - Two Sum / Three Sum (sort + two pointers for the latter)\n"
                "  - Subarray Sum Equals K (prefix sums in a map)\n"
                "  - Group Anagrams (sorted word as the key)\n"
                "  - First Non-Repeating Character (frequency map)\n\n"
                "COMMON MISTAKE\n"
                "Inserting the value into the map *before* checking for its complement — that lets an "
                "element pair with itself and produces wrong answers for targets like 2*nums[i]."
            ),
            'visibility': 'all',
        },
        {
            'title': 'Sliding Window Technique — Cheat Sheet',
            'subject': 'Algorithms',
            'description': 'Fixed vs variable windows, with the exact template used in the coding section.',
            'content': (
                "WHEN TO USE\n"
                "The problem asks for a contiguous subarray/substring that is longest / shortest / "
                "satisfies some constraint.\n\n"
                "VARIABLE-SIZE TEMPLATE\n"
                "    left = 0\n"
                "    state = {}\n"
                "    best = 0\n"
                "    for right in range(len(s)):\n"
                "        # 1. expand: include s[right] in state\n"
                "        # 2. shrink while the window is invalid:\n"
                "        while invalid(state):\n"
                "            # remove s[left] from state\n"
                "            left += 1\n"
                "        # 3. record the answer\n"
                "        best = max(best, right - left + 1)\n\n"
                "FIXED-SIZE TEMPLATE\n"
                "Add s[right]; once (right - left + 1) == k, record the answer and slide by removing s[left].\n\n"
                "COMPLEXITY\n"
                "Each pointer only moves forward, so both traverse the array at most once -> O(n).\n\n"
                "CLASSIC PROBLEMS\n"
                "  - Longest Substring Without Repeating Characters\n"
                "  - Minimum Window Substring\n"
                "  - Maximum Sum Subarray of Size K\n"
                "  - Longest Repeating Character Replacement"
            ),
            'visibility': 'all',
        },
        {
            'title': 'Mid-Semester Exam — Syllabus, Pattern & Instructions',
            'subject': 'Exam Guidelines',
            'description': 'Read this before entering the exam room. Covers the marking scheme and proctoring rules.',
            'is_pinned': True,
            'content': (
                "PATTERN\n"
                "  Section A — 5 shuffled MCQs (order and options randomised per candidate)\n"
                "  Section B — 2 programming problems evaluated on algorithmic logic\n\n"
                "MARKING\n"
                "  MCQ: full marks for a correct option, no penalty for leaving it blank.\n"
                "  Coding: full marks when your logic matches an accepted approach, partial marks for a\n"
                "  near-miss, and zero for a stub or unparsable code.\n\n"
                "REFERENCE SOLUTIONS\n"
                "  If your coding logic is judged incorrect or partially correct, the faculty reference\n"
                "  solutions (with full explanations) unlock on your result page so you can learn the\n"
                "  optimal approach.\n\n"
                "PROCTORING RULES — PLEASE READ\n"
                "  * The exam runs in enforced fullscreen. Leaving fullscreen is recorded.\n"
                "  * Switching tabs or applications is recorded as a violation.\n"
                "  * Keyboard shortcuts, copy/paste and right-click are disabled inside the exam room.\n"
                "  * After the configured number of violations your paper is submitted automatically.\n"
                "  * Your answers auto-save to the server, so an accidental refresh will not lose work.\n\n"
                "SYLLABUS\n"
                "  Arrays and strings, hash maps and sets, two pointers, sliding window,\n"
                "  sorting, and asymptotic analysis."
            ),
            'visibility': 'all',
        },
        {
            'title': 'Recursion & Backtracking Fundamentals',
            'subject': 'Algorithms',
            'description': 'Base cases, recurrence relations, and the standard backtracking skeleton.',
            'content': (
                "THREE RULES OF RECURSION\n"
                "  1. Every recursive function must have a base case that returns without recursing.\n"
                "  2. Each recursive call must move strictly closer to the base case.\n"
                "  3. Trust the recursion — assume the sub-call returns the correct answer for its input.\n\n"
                "BACKTRACKING SKELETON\n"
                "    def backtrack(path, choices):\n"
                "        if is_solution(path):\n"
                "            results.append(path[:])   # copy!\n"
                "            return\n"
                "        for choice in choices:\n"
                "            if not is_valid(choice, path):\n"
                "                continue\n"
                "            path.append(choice)       # choose\n"
                "            backtrack(path, next_choices(choices, choice))\n"
                "            path.pop()                # un-choose\n\n"
                "THE #1 BUG\n"
                "Appending `path` instead of `path[:]`. Since `path` is mutated in place, every stored\n"
                "result ends up pointing at the same (eventually empty) list.\n\n"
                "MEMOISATION\n"
                "If the recursion re-solves identical subproblems, cache them. `functools.lru_cache` turns\n"
                "an exponential naive fibonacci into a linear one with a single decorator."
            ),
            'visibility': 'all',
        },
    ]

    created_notes = 0
    for nd in notes_data:
        _, was_created = FacultyNote.objects.get_or_create(
            title=nd['title'],
            defaults={**nd, 'uploaded_by': faculty, 'department': faculty.department,
                      'is_published': True}
        )
        if was_created:
            created_notes += 1
    print(f"Created {created_notes} Faculty Notes (study material).")

    # ------------------------------------------------------------------
    # 8. Sample personal notes for the first student
    # ------------------------------------------------------------------
    demo_student = students[0]
    personal_notes = [
        {
            'title': 'Revision checklist before the exam',
            'subject': 'Algorithms',
            'tags': 'revision, checklist, priority',
            'color': 'amber',
            'is_pinned': True,
            'content': (
                "[x] Big-O of all sorting algorithms\n"
                "[x] Two-sum hash map template\n"
                "[ ] Sliding window - shrink condition still confuses me\n"
                "[ ] Practice: Minimum Window Substring\n"
                "[ ] Revise recursion tree -> complexity derivation\n\n"
                "Ask Prof. Sharma: does partial marking apply if the approach is right but there is an off-by-one?"
            ),
        },
        {
            'title': 'Sliding window — my own notes',
            'subject': 'Algorithms',
            'tags': 'sliding-window, pattern',
            'color': 'blue',
            'content': (
                "The bit I keep forgetting: the WHILE loop shrinks, the FOR loop expands.\n\n"
                "Expand always. Shrink only while the window is invalid.\n"
                "Record the answer AFTER shrinking, because only then is the window valid.\n\n"
                "For 'longest' problems -> record after the while loop.\n"
                "For 'shortest' problems -> record inside the while loop, just before shrinking."
            ),
        },
        {
            'title': 'Mistakes I made in the last practice test',
            'subject': 'Data Structures',
            'tags': 'mistakes, review',
            'color': 'rose',
            'content': (
                "1. Used `list.remove(x)` inside a loop -> O(n^2). Should have used a set.\n"
                "2. Forgot that dict preserves insertion order in Python 3.7+, wasted time sorting keys.\n"
                "3. Off-by-one in binary search: use `while left <= right` with `right = len(a) - 1`.\n"
                "4. Returned the value instead of the index in Two Sum. Read the output format!"
            ),
        },
    ]
    created_personal = 0
    for pn in personal_notes:
        _, was_created = StudentNote.objects.get_or_create(
            student=demo_student, title=pn['title'], defaults=pn
        )
        if was_created:
            created_personal += 1
    print(f"Created {created_personal} personal notes for {demo_student.enrollment_no}.")

    print("Seed complete!")

if __name__ == '__main__':
    seed()
