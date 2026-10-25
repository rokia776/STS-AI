# Test questions for the HDU (fictional university) chatbot

**Do not put this file inside `data/`.** It contains the answers and would contaminate the knowledge base.

Data files used: `HDU_Student_Handbook_2026-27.pdf` (Handbook), `HDU_Course_Catalog_2026-27.pdf` (Catalog), `HDU_Tuition_and_Scholarships_2026-27.md` (Tuition), `HDU_Tuition_Policy_2025-26_SUPERSEDED.txt` (Archive), `HDU_Student_FAQ.txt` (FAQ), `HDU_Student_Services_AR.md` (Services, Arabic).

## A. Simple lookups (one file)

| # | Question | Expected answer | File |
|---|---|---|---|
| A1 | When do classes start in Fall 2026? | Sunday 20 September 2026 | Handbook |
| A2 | What is the last day to add or drop courses in Spring 2027? | Thursday 25 February 2027 | Handbook |
| A3 | What is the withdrawal (W) deadline for Fall 2026? | Thursday 26 November 2026 | Handbook |
| A4 | What CGPA puts a student on academic probation? | Below 2.0 | Handbook |
| A5 | What happens if I am absent from more than 25% of a course? | Grade DN, no final exam, counts as F | Handbook |
| A6 | Who teaches CAI-310 and when is it offered? | Dr. Karim Nabil, Spring, Mon and Wed 13:00 to 14:30 | Catalog |
| A7 | Which courses are offered in the Summer? | CAI-101, MAT-101, GEN-101, BUS-101 | Catalog / FAQ |
| A8 | How many credit hours is CAI-301? | 4 (3+1 with a lab) | Catalog |
| A9 | How many credit hours are needed to graduate from Computing and AI? | 132 | Handbook |
| A10 | What is the registration fee for a Fall semester? | 1,500 EGP | Tuition |
| A11 | How much is an official transcript and how long does it take? | 100 EGP, 3 working days | FAQ |

## B. Multi-step questions (need more than one file or several lookups)

| # | Question | Expected answer |
|---|---|---|
| B1 | I want to take CAI-310 in Spring 2027. Which courses must I have passed first? | CAI-301, which needs CAI-201 and CAI-250, which need CAI-101 and CAI-102. Full chain: CAI-101, CAI-102, CAI-201, CAI-250, CAI-301, then CAI-310 (Catalog). Each prerequisite needs a grade of C or higher (Handbook / Catalog). |
| B2 | I am on academic probation and hold the Merit Scholarship. How many credit hours can I take and what happens to my scholarship? | Maximum 12 credit hours (Handbook). The Merit Scholarship is suspended while on probation (Tuition, Handbook). It can be reinstated from the semester after returning to good standing. |
| B3 | I completed 85 credit hours and passed CAI-301. Can I register for CAI-401 next Fall? | No. CAI-401 requires 90 completed credit hours in addition to CAI-301 (Catalog). |
| B4 | I am a Business student who wants to switch to Engineering. What do I need and what tuition will I pay after the switch? | At least 24 credit hours and a CGPA of at least 2.5 (FAQ). The Engineering rate, 4,800 EGP per credit hour, applies from the semester after the change is approved (FAQ, Tuition). |
| B5 | I live in Alexandria and have the Entry Excellence Scholarship. Can I get university housing, how much is a double room, and does my scholarship cover it? | Yes, I am from outside Greater Cairo and Excellence holders have priority. A double room is 11,000 EGP per person per semester. The scholarship does not cover housing; discounts apply to tuition only (Services, Tuition). |
| B6 | A student is on academic probation. Must they meet their advisor? | Yes, at least once per semester (Handbook, Services). |
| B7 | I missed an exam because I was in hospital. What must I do and how much will it cost? | Submit a request with documents within 3 working days (Handbook, FAQ). The make-up fee is 300 EGP but it is waived if the head of the department approves the hospital documents (FAQ). |

## C. Calculations

| # | Question | Expected answer |
|---|---|---|
| C1 | A Computing and AI student registers for CAI-201, CAI-250, CAI-301 and GEN-101 in Fall. What is the total cost with no scholarship? | 12 credit hours x 4,200 = 50,400 EGP tuition. Fees: 1,500 + 400 + 600 (lab of CAI-301) = 2,500. **Total 52,900 EGP.** |
| C2 | Same student, but with the Entry Excellence Scholarship. | Tuition 25,200 EGP. Fees stay 2,500 EGP. **Total 27,700 EGP.** |
| C3 | Same student (no scholarship) uses the installment plan. What are the two payments? | Tuition 50,400 + 3% (1,512) = 51,912 EGP, split into two equal parts of 25,956. First payment: 25,956 + all fees 2,500 = **28,456 EGP** on 10 September 2026. Second payment: **25,956 EGP** by Thursday 29 October 2026. |
| C4 | The student in C1 completely withdraws from the university in week 3. How much is refunded? | 50% of tuition = **25,200 EGP**. Fees are not refunded. |
| C5 | The same student drops only CAI-250 in week 1. How much tuition is removed? | 3 x 4,200 = **12,600 EGP**. |
| C6 | What is the total cost of the recommended first Fall semester for an Engineering student, with no scholarship? | ENG-102 (4), MAT-101 (3), CAI-101 (3), GEN-101 (2), GEN-110 (2) = 14 credit hours. 14 x 4,800 = 67,200 + fees (1,500 + 400 + 600 lab of ENG-102) = **69,700 EGP**. |
| C7 | A Business student takes the recommended first Fall semester. What is the total cost? | 13 credit hours x 3,600 = 46,800 + fees (1,500 + 400, no lab) = **48,700 EGP**. |
| C8 | Semester grades: CAI-201 A (3 credit hours), CAI-250 B+ (3), CAI-301 B (4), GEN-101 A- (2). What is the GPA and is the student on the Dean's List? | (4.0x3 + 3.3x3 + 3.0x4 + 3.7x2) / 12 = 41.3 / 12 = **3.44**. Not on the Dean's List (needs 3.5 or above). Also not eligible for the Merit Scholarship, which needs a CGPA of at least 3.7 (Tuition). |
| C9 | A CAI student has the Entry Excellence Scholarship (50%) and also wins a 30% Need-Based Grant. They take 12 credit hours. What is the tuition? | 50% + 30% = 80%, but the total discount is capped at 60%. Tuition 50,400 x 40% = **20,160 EGP** (fees are extra). |

## D. Old vs new policy (the Archive file is a trap)

| # | Question | Expected answer | Wrong answer to watch for |
|---|---|---|---|
| D1 | What is the tuition per credit hour for Business? | 3,600 EGP | 3,300 EGP |
| D2 | What percentage of tuition is refunded on complete withdrawal in week 2? | 80% | 70% |
| D3 | What is the Merit Scholarship CGPA requirement? | 3.7 | 3.8 |
| D4 | How much is the lab fee? | 600 EGP per lab course | 500 EGP |

## E. Arabic and cross-language

| # | Question | Expected answer |
|---|---|---|
| E1 | كم سعر الغرفة المزدوجة في السكن الجامعي؟ | 11,000 جنيه للفرد في الفصل الدراسي |
| E2 | ما هي ساعات عمل المكتبة؟ | الأحد إلى الخميس 08:00 إلى 20:00، السبت 10:00 إلى 16:00، الجمعة مغلقة |
| E3 | كم رسوم اشتراك المواصلات؟ | 2,500 جنيه للفصل الدراسي |
| E4 | ما الحد الأدنى للمعدل التراكمي المطلوب للتخرج؟ | 2.0 (مع تقدير C على الأقل في المواد الأساسية للتخصص) |
| E5 | هل ينطبق خصم المنحة على رسوم السكن؟ | لا، الخصم على المصروفات الدراسية فقط |
| E6 | (English question about the Arabic file) How much is the housing deposit and when is it returned? | 3,000 EGP, returned when leaving housing after graduation or leaving the university, if there is no damage |

## F. Questions with no answer in the data (the bot should say it does not know)

| # | Question | Expected behavior |
|---|---|---|
| F1 | What is the university's world ranking? | Says the information is not available |
| F2 | How much is parking? | Says the information is not available |
| F3 | What is on the cafeteria menu? | Says the information is not available |
| F4 | When is the graduation ceremony? | Says the information is not available |
| F5 | How much is tuition for international students? | Says the information is not available |
| F6 | Does HDU have a Faculty of Medicine? | Documents list only three faculties (Computing and AI, Business, Engineering); it should not invent a medical faculty |

## How to judge the results

- **A**: basic retrieval and reading.
- **B and C**: the main test for Agentic RAG. A plain RAG often retrieves only part of the needed information; an agent should search again for each missing piece.
- **D**: checks that the answer uses the 2026-2027 document, not the archived one.
- **E**: checks the multilingual embeddings (`bge-m3`) and answering in the language of the question.
- **F**: checks honesty. Inventing an answer counts as a failure.
- For every answer also check that the cited sources are the right files.
