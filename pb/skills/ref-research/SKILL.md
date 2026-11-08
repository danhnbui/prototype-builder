---
name: ref-research
description: The method for validating what a project is unsure about with real people in Product Builder — defining the question and the decision a study informs, choosing among survey, interview, usability test, tree test, card sort and first-click, writing the research plan (recruiting, screeners, sample size per method, schedule, roles, pilots) and the logistics (participant tracker, consent, incentives, recording, moderated vs unmoderated), turning a job's when/want/so and a flow's path into past-behaviour questions and realistic task scenarios, the question-writing rules and the bias list, the five standard metrics (CES, SEQ, CSAT, NPS, SUS), reading the computed analysis (success rates with intervals, time on task, lostness, dead clicks, SEQ, SUS), synthesis into observations, themes and severity-rated issues, and reporting without fooling yourself. Use when writing a study's plan, hypotheses and instrument and when synthesizing and reporting its evidence — loaded by /pb:research §1. Not for the tool's commands and gates (/pb:research), usability heuristics on a design (think-layout), or scoring design options (ref-design-compare).
user-invocable: false
---

# ref-research

A study is sound when it could have told you that you were wrong. Most do not: the questions invite the
answer the author wants, the sample is whoever was easy to reach, and the write-up counts the quotes that
agree. This skill is the discipline that stops that, and the method a senior UX researcher follows from
the first framing of the question to the last line of the report. The tool checks structure and
arithmetic; **nothing here is checked for you**, so read §5 and §17 twice.

Provenance: Portigal, *Interviewing Users* (interviews); Fitzpatrick, *The Mom Test* (asking about past
behaviour, not opinions of your idea); Krug, *Rocket Surgery Made Easy* (small, repeated usability
sessions); Krosnick & Presser, "Question and Questionnaire Design" (*Handbook of Survey Research*, 2nd ed.;
wording, order, response scales); Christensen and Ulwick on jobs-to-be-done (a job is a situation and an
outcome); Rubin & Chisnell, *Handbook of Usability Testing* (2nd ed.; test plans, task scenarios,
think-aloud, moderating, reporting); Dumas & Loring, *Moderating Usability Tests* (facilitation, when not
to help); Sauro & Lewis, *Quantifying the User Experience* (2nd ed.; the adjusted-Wald interval, the
geometric mean for task times, SEQ and SUS, the curved SUS grades); Tullis & Albert, *Measuring the User
Experience* (3rd ed.; task success, time, lostness, self-reported metrics, reporting); Spencer, *Card
Sorting: Designing Usable Categories* (open and closed sorts, reading results); Tullis & Wood, "How Many
Users Are Enough for a Card-Sorting Study?" (the case for about 15); Nielsen, *Usability Engineering* and
the Nielsen Norman Group article on severity ratings (the 0 to 4 scale and its three factors); Nielsen &
Landauer (1993) and Nielsen's later "Why You Only Need to Test with 5 Users" (the small-sample argument,
which is contested and applies only to finding problems); Brooke (1996) for the System Usability Scale.
Sample sizes in §8 and benchmarks in §15 are rules of thumb stated as such, not results from those books.
The cost of being wrong is high and the numbers are easy to over-read, so where a figure is in doubt this
skill leaves it out.

## 1 · Choose the method

Two questions place a method. Is the evidence **behavioural** (what people do) or **attitudinal** (what they
say, believe or prefer)? Is it **qualitative** (why, how, what went wrong) or **quantitative** (how many,
how much)? Behaviour beats opinion when you can observe it (§4).

| The question | Use | Behavioural / attitudinal | Qual / quant | Why |
|---|---|---|---|---|
| Why do they do it? How? What goes wrong? What do I not know to ask? | **Interview** | attitudinal, about past behaviour | qual | Open, follows the person, finds things you did not think of |
| Can they finish this flow on the prototype? Where do they stumble? | **Usability test** (an interview with tasks) | behavioural | qual (a handful) or quant (success, time, with an interval) | You watch what they do, not what they say they would do |
| How many? How often? Which of these? | **Survey** | attitudinal | quant | Counts across more people, on something you already understand |
| Can people find where a thing lives in this structure, with no visual design to help? | **Tree test** | behavioural | quant | Isolates the labels and the hierarchy; says where the structure fails, not why |
| How do people group these things, and in what words? | **Card sort** (open, closed or hybrid) | attitudinal (mental model) | qual and quant | Gives vocabulary and groupings as input to a structure, never the structure itself |
| Would a first click on this screen go the right way? | **First-click test** | behavioural | quant | One click per task is a cheap, strong predictor of finding the thing |
| I am not sure what the options even are | **Interview first** | attitudinal | qual | A survey can only measure the options you listed |

Listed in the tool's catalog but with no runner here: diary study, contextual inquiry, concept test,
five-second test. They are real methods; the tool will not run them. Name them in the plan when one fits.

**Decision path.** Take the first line that is true.

1. Do not know what the problem or the options are? **Interview.**
2. Know the options and want to know how many, how often or which? **Survey.**
3. Question is about structure and wording of navigation: **where would they look?** Start with a **card
   sort** to learn how people group and name things, then a **tree test** on the structure you built from it.
4. Question is whether someone can do something on a screen or flow? **Usability test.** One screen and one
   "where would you click" question: **first-click.**
5. Question is whether a design works better than another? Not these methods alone; use `ref-design-compare`
   to score options, and test the winner here.

If you can list the answer options without asking anyone, a survey can size them. If you cannot, interview.

## 2 · Plan and define

Most weak studies are weak here, before a single question is written.

**A business question is not a research question.** "Should we launch the new checkout?" is a business
question; research cannot answer it. "Can first-time buyers complete checkout without help, and where do
they stop?" is a research question: specific, about people, answerable with evidence. Write both, and keep
the first only as the reason the study exists.

**Name the decision.** Finish the sentence "If we learn X we will do A, if we learn Y we will do B."
A study with no decision attached produces a report nobody acts on. If no result would change anything,
do not run it. This is `plan.decision`.

**Objectives and research questions.** Two to four objectives (what you want to understand), each broken
into questions a participant's behaviour or words can answer (`plan.objectives`, `plan.researchQuestions`).
A research question that begins "Do users like" is not one.

**Hypotheses with thresholds fixed before data.** A hypothesis is a prediction that could be wrong, with
`supportedIf` and `refutedIf` written at G-STUDY and never moved afterwards. Write them in counts at small
n, because a percentage from five people means little (§16).

| Method | A hypothesis written so it can fail |
|---|---|
| Usability | "Supported if at least 4 of 5 first-time orderers reach confirmation unassisted; refuted if 2 or more cannot." |
| Tree test | "Supported if at least 70% of participants choose the Refunds branch for the lost-parcel task; refuted if fewer than 50% do." (State the interval you will read, §16.) |
| Card sort | "Supported if the 'Change booking' and 'Cancel booking' cards sit in one group for most participants." |
| First-click | "Supported if at least 80% of first clicks land on the Pay button." |
| Interview | "Supported if at least 4 of 6 couriers describe settling cash at the end of the day without being asked." |

**Method rationale.** Say why this method and not the neighbouring one (`plan.methodRationale`): what it
can show, what it cannot, and what you will not claim. A reviewer should be able to disagree with the
choice, not just with the result.

**What each method can and cannot tell you.**

| Method | Can tell you | Cannot tell you |
|---|---|---|
| Interview | Why, how, what happened last time; things you did not think to ask | How many people; whether a design works |
| Survey | How many and how often, on options you listed | Why; what people do rather than report |
| Usability test | Where a task breaks, what people expected, how long it takes | How many people in the market have the problem; whether they would choose it |
| Tree test | Whether labels and hierarchy let people find an item | How the page looks or reads; whether people will start from that page |
| Card sort | The words and groupings people bring | The right structure; which grouping is best for the business |
| First-click | Whether the first move is right | What happens on the second; why a click was wrong |

**Formative or summative.** *Formative* work finds problems while the design can still change: small n,
qualitative, fast, repeated. *Summative* work measures how well a finished design performs against a
target: larger n, tight thresholds, intervals, one pass. Most prototype studies are formative. Calling a
formative study summative ("90% success") is the commonest overclaim. Say which it is in the plan.

## 3 · From jobs and flows to questions

The registry already states what to ask:

- A job's **`when`** is the trigger. Ask for the last time it happened: "Tell me about the last time you
  <when>." The **`want`** and **`so`** become "what did you do, and what were you trying to get done?"
- A story's **path** is a task. Put the person on the prototype at the story's start, state the goal, and
  watch. Do not say which screen or button.
- A rule's **`ASSUMPTION`** is a prediction about behaviour. Ask what people do that the assumption
  predicts. If the rule says couriers settle cash daily, ask when they last settled cash, not whether they
  like daily settlement.
- A role or segment is **who you screen for**, not a label on the report.

Every question tests a hypothesis; a question that tests none is curiosity, so cut it or move it to
warm-up. Write the hypothesis first with its `supportedIf` and `refutedIf` (§3 of the command).

## 4 · Past behaviour over opinion

People are poor at predicting what they would do and good at reporting what they did.

| Ask about | Not about |
|---|---|
| the last time it happened | what usually happens, or what they would do |
| what they actually did, in order | what they think of your idea |
| what it cost them (time, money, a workaround) | whether they would pay for it |
| what they use today | what they would switch to |

Compliments, "that would be great" and "I would definitely use that" are not evidence. A specific past
episode, a workaround they built, or something they spent money on is.

## 5 · Writing a question

One thing per question. Neutral wording. Plain words the audience uses. A time frame when it is about
behaviour. Options that are exhaustive and do not overlap.

| Bad | Why | Better |
|---|---|---|
| "Don't you think the cash screen is confusing?" | leading | "Tell me about the last time you handled cash. What did you do first?" |
| "How easy and fast is checking out?" | double-barrelled | Ask two questions, or "Which part of checking out took longest?" |
| "Would you use a reminder feature?" | hypothetical | "Last week, did you miss a settlement deadline? What happened?" |
| "Do you agree the app saves you time?" | acquiescence (agree/disagree) | "About how long did settling cash take you today?" (options as minutes) |
| "How often do you check your balance?" with Never / Sometimes / Often | vague, unanchored | "In the last 7 days, on how many days did you check it?" |
| "Do you eat healthily?" | social desirability | "What did you eat yesterday?" |
| "Bạn có thấy màn hình thanh toán dễ dùng không?" (Do you find the payment screen easy to use?) | leading, yes/no | "Lần gần nhất bạn thanh toán, bạn bắt đầu bằng thao tác nào?" (The last time you paid, what did you do first?) |
| "Bạn có muốn có tính năng nhắc hạn không?" (Do you want a deadline reminder?) | hypothetical | "Tuần trước bạn có trễ hạn nộp tiền thu hộ không? Chuyện gì đã xảy ra?" (Last week, were you late settling collected cash? What happened?) |
| "Bạn thấy ứng dụng nhanh và dễ dùng không?" (Is the app fast and easy?) | double-barrelled | "Việc nào trong ứng dụng mất nhiều thời gian nhất với bạn?" (What takes you the longest in the app?) |

**Bias list. Check every question against it.**

- **Leading.** The wording signals the right answer. Strip adjectives and "don't you".
- **Double-barrelled.** "and" or "or" joins two things; one answer cannot serve both.
- **Hypothetical.** "Would you", "if we built". Replace with what they did.
- **Acquiescence.** Agree/disagree and yes/no invite yes. Ask for the fact or the choice instead.
- **Order.** An earlier question primes a later one. Put general before specific, behaviour before
  opinion, and the feature under test late. Randomise the options of a multiple-choice list when order is
  not meaningful (§6).
- **Social desirability.** People report what looks good. Ask about a specific past episode and make the
  unflattering answer easy ("Many people skip this. Did you last week?" can itself lead, so prefer
  "Last week, how many times did you ...?").
- **Sunk cost of the author.** You built it, so you hear praise and explain away trouble. Write the
  `refutedIf` before you field. In a session, never defend the design or explain it; a user who is
  confused is the data.
- **Naming the feature early.** A question that names the thing under test before the task has told the
  person what to look for. Describe the goal, not the feature.

## 6 · Building the instrument

### Survey
- **Screener first.** Questions that decide whether this person is in the audience, with the qualifying
  answers listed (`qualifies`). Disqualified rows are dropped and counted; say how many.
- **Length.** Aim for under about 5 minutes and 15 questions. Every extra question loses people. Keep
  free-text to a few; the tool counts text answers, it does not summarise them.
- **Scales.** One scale type through the survey (say 1 to 5), always the same direction, with both ends
  labelled in words and a midpoint if neutral is a real answer. A frequency is better as a number of days
  than as "often". Do not mix "1 is best" with "5 is best".
- **Options.** Exhaustive and mutually exclusive, with "Other (please say)" or "None of these" where it
  is a real answer. Never an "Other" you would not read.
- **Randomise** the option order of unordered lists and of question blocks that do not depend on one
  another, in the tool you field it in; pb cannot do it for you. Keep scales and screener fixed.
- **Test it** on one real person from the audience before sending it widely, and expect to change it.

### Interview guide
- **Warm-up** (2 to 3 minutes): who they are, what their work looks like. Easy, factual, builds ease.
- **Story**: "Tell me about the last time ..." then follow the thread: "What happened next?" "How did
  you decide?" "What did you do instead?"
- **Task with think-aloud**: state the goal, ask them to say what they are looking at and thinking, and
  stop talking. Do not hint, point or answer questions about the interface ("What would you do if I
  weren't here?"). Note where they hesitate, go wrong or give up. Agree what success is beforehand. For
  a study that is mostly tasks, use the usability test (§11).
- **Probes** (write them in advance, use them when needed): "Can you say more?" "What do you mean by
  that?" "Can you show me?" "What did you expect to happen?"
- **Silence.** Wait 5 seconds after an answer. People fill silence with the useful part.
- **Not defending the design.** When they criticise, say "thank you, tell me more". Never explain why it
  is like that.
- **Close**: "Is there anything I did not ask that I should have?" and thank them.
- About 30 to 45 minutes per session; shorter for a single task.

## 7 · Prepare the plan

The research plan is one short document the team can disagree with before anyone is recruited. In the
tool it is the study's `plan`; every field has a reason.

| Plan field | What goes in it |
|---|---|
| `background` | What is already known and why the question came up now; two or three sentences |
| `objectives`, `researchQuestions` | From §2; not more than the schedule can answer |
| `decision` | The decision the study informs and who makes it |
| `methodRationale` | Why this method, what it cannot tell you |
| `participants` | `criteria` to include, `exclude` list, target `n` per segment, the `segments` |
| `recruitment` | `channel`, `incentive`, and a `note` on what could bias who comes |
| `schedule` | `start`, `end`, `sessionMinutes`, with room for the pilot and for no-shows |
| `team` | `moderator`, `notetaker`, `observers` (§9) |
| `materials` | Consent, screener, moderator guide, tasks, note-taking sheet, the prototype build under test |
| `risks` | Each as a risk and its mitigation (§9 lists the usual ones) |
| `timeline`, `budget` | Milestones with dates; incentives, tools, time |

**Recruiting and the screener.** Recruit on **what people do**, not who they are. "Ordered food for a group
at least twice in the last month" finds the right person; "aged 25 to 40" mostly does not. Screen on
behaviour, recency and tools in use, and keep the criteria hidden: a screener that reveals what you want
invites people to say yes. Exclude people with a stake in the design (colleagues, people who built it,
people recently in a similar study) and anyone who could not freely say no. Say plainly how people were
reached, because who answers is a limit (§8). **Over-recruit**: expect a share of no-shows, and book
extras or standby slots rather than finding out on the day you have three of five.

**Sample size per method** is in §8; read it before you set `n`.

**Schedule.** Work back from the decision date. Leave a day for the pilot and its fixes, buffer for
no-shows, and time after the last session for analysis and synthesis, which take longer than the sessions
themselves. A moderated hour needs about an hour of note work behind it.

**Roles.** Even a team of one holds all three; say who does what.

- **Moderator** runs the session, reads the script, gives no help, keeps time. Does not take notes beyond
  a glance.
- **Note-taker** records observations as they happen, with a time stamp and the task, separate from
  interpretation (§18). If the session is recorded, notes are an index into it.
- **Observers** watch live from another room or window, silent. Their rules: no talking to the participant,
  no commenting where the participant could hear, no laughing, write issues down rather than blurting
  solutions, and hold conclusions until the debrief. An observer who leaps to a fix after one session is
  the usual way a study loses its credibility.

**Pilot, always.** Run the whole session once with someone who is not on the team, in the real set-up,
with the real recording. Check that the tasks read as intended, the timing holds, the success definitions
work, the consent and recording run, and the prototype survives. Fix what it shows. **A pilot is never
evidence:** keep it out of the findings, tally and report, whatever it showed, and label it a pilot in the
tracker. A pilot that changes the tasks means the next sessions are the first real ones.

## 8 · Sample size, said honestly

These are rules of thumb, not statistics. They set what you may claim.

| Method | Rule of thumb for `n` | What that buys |
|---|---|---|
| Usability test, formative | about 5 per segment, repeated across rounds | Most of the common problems in a flow; no percentage |
| Interview | about 5 per segment | Patterns in why and how; no percentage |
| Survey | about 30 or more | Directional counts below that; more for any subgroup comparison |
| Tree test | about 50 | A success rate with an interval narrow enough to compare two structures |
| Card sort, open | about 15 | Stable-looking groupings; Tullis & Wood is the usual source for this |
| First-click | about 30 | A click map and a hit rate you can read with an interval |

- **About 5 interviews or test sessions per segment** will usually surface most of the usability problems
  in a flow, and that is all they do. They do not tell you how many people have a problem. **Never report
  a percentage from interviews or a five-person usability test without its interval** (§16). Say "3 of 5
  participants".
- **More segments, more people.** 5 per segment, not 5 total. A difference between segments needs
  enough in each segment to see it.
- **A survey under about 30 respondents is directional only.** Say "directional" next to every number.
  With a small base, one respondent moves a percentage by several points.
- **Below the number in the table, the result is directional.** Say so on the number, in the chart and in
  the limitations.
- **Always report n**, per question when it differs, and the number excluded by the screener.
- **A segment-wise comparison needs n per segment**, stated for each group. Do not compare 12 people with 4.
- **Who answered is a limit.** People who answer a survey, or agree to an interview, differ from those who
  do not. Say who you reached and how.
- **One participant is an anecdote.** Say it is, and do not build a verdict on it.

## 9 · Logistics

The study fails on logistics more often than on method. The tool keeps a checklist and a participant
tracker; work the list, do not trust memory.

**Participant tracker.** One row per person, by pseudonym only (`P01`, `P02`), with segment, role, status
(invited, screened, scheduled, done, no-show, withdrawn, excluded), session date, incentive status and
whether the session was a pilot. Real names, emails and phone numbers live in your own scheduling tool,
not here, and the tracker refuses a value that looks like one. Keep the mapping from pseudonym to person
outside the project, and delete it when the study closes.

**Consent before recording.** Consent is asked and recorded **before** anything is captured, in words the
person understands: what is recorded (screen, voice, clicks), who will see it, how long it is kept, that
they can stop or withdraw at any time without losing the incentive. Recording is a **separate, optional**
choice from taking part. No consent, no data (§10).

**Incentives.** Decide the amount and form in the plan, pay at the end of the session whether or not the
person finished the tasks, and say beforehand that payment does not depend on how well they did. Set
the status to paid in the tracker. An incentive should compensate time, not buy a good opinion.

**Equipment and recording check.** Before each session: prototype opens on the machine used, screen
share and microphone work, the browser permissions are granted, there is free disk space, and a test clip
plays back with voice. Run the check on the session machine, not a different one. Have a plan B if the
recording fails: keep running the session and note by hand, rather than abandoning the participant.

**Moderated or unmoderated.**

| | Moderated | Unmoderated |
|---|---|---|
| You get | Why: you can probe, see hesitation, recover from a broken moment | Scale and speed: many people, no scheduling |
| You lose | Time per person; some moderator influence | The probe; you cannot tell why, or rescue a participant who is stuck |
| Best for | Formative usability, interviews, anything with unclear tasks | Tree test, card sort, first-click, well-defined tasks with a clear success test |
| Needs | A moderator, a note-taker, a slot | A kit that works on a clean machine, tasks that read without you, a brief that stands alone |

**Remote or in person.** In person gives you the room, body language and no network trouble; it costs
travel and limits who comes. Remote reaches more people and fits their own device, at the cost of
technical failures and a thinner read of the person. Use a participant's own device and set-up when the
study is about their real context. Whichever you choose, test the link or the room beforehand.

**Observer etiquette.** Brief observers before the first session (§7). Their view is read-only. Decide how
they pass questions to the moderator (a note, not an interruption), and keep their number small; a room
full of observers changes what the participant does.

**The participant kit (unmoderated).** A kit is one self-contained file you send, so the participant needs
no account and nothing is hosted. It must make sense with you absent: what the study is, how long it takes,
what is recorded and how to stop, how to send the result back. Open the kit on a clean machine before
sending it. Participants send back a session file, and a video if they agreed to record; import both, and
treat anything that fails to import as a no-show to chase, not data to retype.

**Data minimisation.** Collect only what the hypotheses need. Do not record when notes would do. Keep
only pseudonymised files in the project. Delete what you no longer need when the study closes.

**Common risks to write into `plan.risks`:** no-shows, a recording that fails, a prototype that breaks on
the day, a participant who is not the target, a stakeholder who cannot sit still as an observer, an
unmoderated task that reads two ways. Each gets a mitigation, not just a name.

## 10 · Ethics and data

- **Consent first**, in words the person understands: what is recorded, who will see it, how it is
  used, and that they can stop or withdraw at any time. Record that they agreed. No consent, no data.
- **Pseudonyms.** `P01`, `P02`. Never a real name in a transcript, a note, a file name or a quote. Leave
  out or remove names, phones, emails and addresses from what you store.
- **Withdrawal.** If someone withdraws, their data leaves the findings. Do not argue them out of it.
- **Minimal data.** Collect only what the hypotheses need. A column you do not use is a liability.
- **Honest framing.** Do not tell participants the study is about something it is not, and do not
  recruit people who could not freely say no (someone whose manager is watching).
- **Never invent people.** A made-up respondent, however plausible, is not research. Real people, or no
  claim. The same goes for a made-up session, click or quote. The rules that do not move are in
  `canon.md` § *Research evidence*.

## 11 · Usability testing

A usability test puts a real person on the prototype with a goal and watches. It finds where the design
fails, not whether it is liked.

### Writing task scenarios
A task is a short story with a goal the person already cares about. The tool does not write it for you.

- **A realistic goal, in the person's words.** "You ordered the same lunch last Tuesday and want it again
  for tomorrow. Get it set up." Not "Use the reorder feature."
- **No interface words.** Never the label of a button, a menu or a screen. If the task contains the word
  on the target, you have run a reading test, not a usability test. Words from the task should be the
  person's, not the product's.
- **No steps.** The route is what you are measuring. "Go to Orders, pick last order, tap Reorder" is
  an instruction, not a task.
- **One goal per task.** Two goals hide which one failed. A task that needs the outcome of an earlier one
  must say what the person has now, so a failure there does not cascade.
- **Give the context needed and nothing else.** Name, budget or date when they matter; write the data
  they would otherwise invent, so everyone does the same task.
- **A success definition agreed before the first session.** Say what the end state is: the screen reached,
  the thing visible, the field filled, and what counts as a wrong answer. The tool can check "criteria
  met" from the screen and the DOM, but you decide what the criteria are. Note the **optimal path** if you
  want to measure lostness (§16).
- **A start screen.** The task starts where a real person would be, not always on the home screen. Set the
  role and entry point when they matter.
- **A time limit** that is generous, so a time-out means something went wrong, not that the clock was
  short.

| Weak | Why | Better |
|---|---|---|
| "Click on Orders and then Reorder." | steps, interface words | "You want last Tuesday's lunch again for tomorrow. Set it up." |
| "Find the refund policy and request a refund." | two goals | Two tasks, each with its own success |
| "Check out." | no goal, no stakes | "You are ordering for four colleagues with a 60 budget each. Place the order." |

### Order and counterbalancing
Start with an easy task so the person settles. Put tasks in the order a real user would meet them when
they depend on one another. When they do not, **vary the order** across participants (counterbalance), so
fatigue and learning do not always fall on the same task; say so in the report. Do not put the task with
the most at stake last and the most tired.

### Think-aloud
Ask the person to say what they are looking at, thinking and expecting while they work.

- **Concurrent** (while working) shows moments of confusion as they happen, and can slow people down and
  change what they do. **Retrospective** (watch the recording afterwards and comment) is cleaner on time
  and path, but memory fills gaps. Concurrent is the usual choice for formative work; use retrospective,
  or none, when times matter.
- **Give a practice task** on something unrelated so they learn to talk. Show it; do not describe it.
- **Neutral prompts only.** When they go quiet: "What are you thinking?" "What are you looking for?"
  "Keep talking." Not "Why did you click that?" while they work (it makes them justify), and never a
  prompt that names the right place.
- **Do not answer questions about the interface.** "What would you do if I weren't here?"

### When to assist, and how to mark it
Stay silent through confusion; confusion is data. Intervene when the person is stuck for a long time with
no sign of recovering, is distressed, or the prototype itself breaks (a broken prototype is not the
participant's failure; note it and restart the task). **Mark every assist** at the moment it happens: an
assisted task is not a success, and the tool counts it separately. Give the smallest hint that lets the
session go on, write down what you said, and never hint on the next task to make up for it.

### What to observe
- **Hesitation** before a click, a long look, hovering without clicking.
- **Wrong turns**: screens visited that are not on the way, and back.
- **Dead clicks**: a click on something that looked clickable and was not. Treat as a signal that a thing
  looks like a control.
- **Errors**: validation messages, failed submissions, wrong choices, slips.
- **Recovery**: whether they noticed, how, and how fast.
- **Said versus done.** Self-reported success and observed success disagree more often than expected.
  Someone who says "that was easy" after failing is data on the design, not noise. Record both; trust the
  observed outcome.
- **Expectation**: what they expected to happen at the point they stopped. Ask after the task, not during.

### After each task and after the test
- **Post-task SEQ**, straight after the task, while memory is fresh. It tells you where to look; a low SEQ
  on a task someone completed is as interesting as a high one on a task they failed.
- **Post-test SUS**, once, after all tasks, for the product as a whole. Never after a single screen.
- A short **debrief**: "What was the hardest part? Anything surprising?" and a last open question.

## 12 · Tree test

A tree test puts only the **text labels of a structure** in front of the person and asks where they would
go to find something. No layout, no search, no visual design: it isolates the labels and the hierarchy.

- **Use it on a structure, not a design.** If the answer depends on the page that carries the labels, this
  is the wrong method.
- **Text-only labels.** The tree is the real hierarchy with real wording. Keep the depth and the breadth
  you intend; a pruned tree tests a different structure.
- **Write the tasks without parroting the labels.** If the label says "Refunds", do not ask "Where do you
  go for refunds?"; ask "Where would you go to get your money back for an order that never arrived?" A task
  that repeats a label tests word matching. Write tasks from jobs, then check each one against the label
  on its correct node.
- **One correct destination, or a few agreed in advance.** Decide the correct node(s) before fielding, the
  way you decide success in a usability test.
- **How many tasks.** About 8 to 10 keeps people attentive. Vary the branches so one branch is not tested
  by every task.

**Reading the results.**

| Measure | Means | Read it as |
|---|---|---|
| **Success** | The person chose a correct node | A rate with an interval (§16); at 50 people it is readable, at 15 it is not |
| **Directness** | Reached the answer without going back up the tree | A direct success says the labels led them; an indirect one means they had to recover |
| **First click** | Which top-level branch they opened first | The strongest early signal: a wrong first branch is the root of most failures |
| **Destinations** | Where people ended, including wrong nodes | Wrong answers cluster; the cluster names the label that competes with the right one |

A low success with high directness means people were confident and wrong: two labels sound alike, or the
right label means something else to them. A low success with low directness means the structure confuses
and people hunt. Read the destinations before you change the structure. Fix labels first and retest; a
tree test is cheap to repeat.

## 13 · Card sort

A card sort asks people to group cards, each a piece of content or a function, and to name the groups. It
shows how they think things belong together and what they call it.

| Kind | People | Use it for |
|---|---|---|
| **Open** | Sort the cards into groups they create and name | Early: you do not know the groups or the words |
| **Closed** | Sort the cards into groups you provide | Later: checking that new content fits the structure you have |
| **Hybrid** | Use your groups, or make their own | Between: you have a draft structure and want to see where it breaks |

- **Number of cards.** About 30 to 60 is typical; 10 to 60 is workable. Fewer than that tells you little,
  more tires people and makes the groupings noisy. A card for everything in the product is a mistake;
  pick what the study needs to learn.
- **Card wording.** Cards that **share a keyword** get grouped by the word, not the meaning ("Order history"
  and "Order status" sit together whatever they do). Vary the words, keep a card to one idea, and use the
  language of the person's task, not internal terms. Add a short description only when a card is
  ambiguous without one, and give every card the same treatment.
- **A mix of cards**, some obvious and some hard, so the sort has something to show.
- **Fifteen is the usual number for an open sort** (§8). Fewer groupings stay stable; more rarely change
  the picture.

**Reading a similarity matrix.** For every pair of cards the tool reports the share of participants who put
both in one group. Pairs near 1 are a strong "go together"; pairs near 0 are not. The tool then merges the
cards into clusters at a cut level. Read it this way:

- **The cut level is a choice.** A low cut yields a few large groups, a high cut many small ones; look at
  more than one before trusting a cluster.
- **Clusters are input to a structure, not a structure.** They show which cards people treat as one thing
  and which labels they reach for. Business rules, depth and the way a screen works also decide the final
  structure. Do not copy a cluster diagram into a sitemap.
- **Cards that sit between clusters** are the useful ones: they belong to two ideas, and they are where a
  cross-link, a second route or a rename is needed.
- **The names people give groups** are vocabulary, and the best source of labels you will find. Collect the
  words that recur, and note the words nobody used.
- **Closed and hybrid sorts report category agreement**: how many people put each card in each category.
  A card that no category wins is a card to move or rename.
- **A sort says how people group, not whether the result is findable.** Test the structure you build from it
  with a tree test (§12).

## 14 · First-click testing

A first-click test shows a screen and asks where the person would click first to do something.

- **Why it works.** The first click sets the path. When it goes the right way, the task usually goes on to
  succeed; when it goes the wrong way, recovery is slower, costs more and often fails. Your own usability
  and tree-test data will show the same pattern. It is a cheap, strong signal and no substitute for the
  whole task.
- **One question per screen.** A screen with three questions teaches the person where the answers are.
  Ask one question, then move on; vary the order across people when there are several screens.
- **A task, not a label.** Write it as a goal, as in §11 and §12, with no word taken from the target.
- **Define the target before fielding:** the element or region that counts as a hit. More than one area can
  be right if the design offers more than one route; agree which.
- **Read the click map as well as the rate.** Where the wrong clicks cluster names the thing that looks
  like the answer. A spread with no cluster means the screen offers no clue.
- **What it cannot tell you:** what happens after the click, or why. Where a first click fails, follow
  with a usability test on that screen.

## 15 · Five standard metrics

Use a standard metric when the question is what it measures, because the wording is fixed and scores can be
compared across studies. Use the template as written: a reworded standard question is no longer the
standard, and a translation is a different instrument (the tool flags it). Only a survey is scored; in an
interview the question is read out and not scored. In a usability test, SEQ and SUS are scored by the
tool from the session.

| Template | Measures | When not to use it | How to read it |
|---|---|---|---|
| `ces` | The **effort** of getting something done over a whole flow | One small step (use `seq`); when you want to know *why* it was hard | The mean, and the share who found it hard. Lower effort is better |
| `seq` | The **ease** of one task, asked straight after it | A whole journey (use `ces`); any time later than right after the task, when memory has blurred | The mean per task. Compare tasks with each other; a low one points at where to look |
| `csat` | **Satisfaction** with an experience | To predict behaviour, or on a prototype nobody has used for real | The share of the top ratings and the mean. It records a mood, not a cause |
| `nps` | Whether people would **recommend** a product they have really used | **A prototype they just saw**: nobody has a basis to recommend it. Also when n is small: the score swings on one person | Promoters minus detractors, with n beside it. Read it with the reasons people give |
| `sus` | **Overall usability** after real use; ten items | Early sketches or a single screen; before people have used it enough to judge the whole | One 0 to 100 score from the ten items, which the tool computes; never read a single item alone |

- **A benchmark is context, not a pass mark.** Published averages come from other products, other
  audiences and other methods. If you mention one, say where it comes from and that it is not a target; if
  you are not sure of a figure, leave it out. The hypothesis's own threshold, written at G-STUDY, is what
  decides a verdict. The score's real use is a comparison: this flow against that one, this version against the last.
- **Report n beside every score**, and call a score from under about 30 people directional (§8).
- **Scores say how much, not why.** Pair a score with a task or an open question that lets people say what
  made it that way.
- **Agree-format is an accepted exception.** `sus`, and some other standard items, ask people to agree or
  disagree, which §5 warns invites a "yes". For these metrics comparability is the point, so keep the
  standard wording and note the exception. Do not copy the format into questions of your own.

## 16 · Analysis: what the tool computes and how to read it

You type none of these numbers (`canon.md` § *Research evidence*). The tool recomputes them from the
evidence whenever it is checked, so a stale number is caught. Your job is to read them honestly.

**Completion rate with an interval.** A rate from a few people is a coin toss with a number on it. The tool
reports the share who succeeded **with an adjusted-Wald 95% interval**, which stays sensible at small n
and at 0% or 100% (Sauro & Lewis). 4 of 5 is 80%, and the interval runs from roughly a third to nearly
everyone; 40 of 50 is also 80%, and the interval narrows to roughly two thirds to nine tenths. The
interval is the finding. **Never report a percentage from five participants without its interval,**
and say "4 of 5" first. Read a threshold against the whole interval: a rate whose interval straddles the
threshold has not met it and has not missed it. A success needs the outcome and no assist.

**Time on task.** Task times are skewed: a few long ones pull the average up. The tool reports the
**geometric mean** (the usual choice at small n, per Sauro & Lewis) with an interval, and the median, for
**successful attempts only**. Failed or abandoned times say only how long they lasted before they stopped
trying. Compare tasks and versions, not a time against an absolute. Time with think-aloud is longer than
time without it.

**Lostness.** From the optimal path and what the person visited: it compares screens visited, distinct
screens and the minimum needed (Smith's lostness, as in Tullis & Albert). **0 means a perfect path; at or
below about 0.4 reads as not lost**; higher reads as hunting. A rule of thumb: use it to find tasks that
sent people wandering, not as a pass mark. It needs an optimal path in the task; one with two valid routes
needs the shorter.

**Clicks, dead clicks, rage clicks, errors.** These are **signals, not verdicts.** A dead click says
something looked clickable. A rage click (three or more fast clicks in one spot) says a thing did not
respond or did not do what was expected. Errors count validation messages and failures. Each points to a
place in the replay worth watching; none says what is wrong. Never write "the button is broken" from a
count; watch the session.

**SEQ.** A 7-point ease rating per task. The mean per task says where to look first. A published average
of around 5.5 is often quoted (Sauro & Lewis); it is context from other products, not a target (§15).

**SUS.** A 0 to 100 score from ten items, computed by the tool. **68 is the commonly cited average.** The
curved grade (Sauro & Lewis) maps the score to a letter on that average: roughly C is about 63 to 72, B about 73
to 80, A about 81 and above, D about 52 to 62, and below about 52 is an F. A SUS from five people has a wide interval, the tool
reports it, and you quote it. A grade is a label on the score, not a finding. Do not average SUS over
different tasks, and never read one item alone.

**Against thresholds fixed at G-STUDY.** The verdict compares the number and its interval with what you
wrote before the data. Supported means the whole interval, or the agreed count, clears the threshold.
Refuted means it falls clearly short. A straddle or a thin sample is inconclusive; say so.

**Below target n is directional.** If the study ran fewer people than the plan's target, every number is
labelled directional in the tables and the report. The tool adds the label; do not remove it, and do not
bury it in the limitations.

**Per method.** Tree test: success, directness, first click, destinations (§12). Card sort: similarity,
clusters, category agreement (§13). First-click: hit rate with interval, time, click map (§14). Survey and
interview answers are tallied as before.

## 17 · Reading results

1. **Code from the transcripts.** Read every one in full. Per participant, note what happened and what
   was said. Group by pattern afterwards; do not start from the categories you hoped for.
2. **Separate observation from interpretation.** Observation: "P03 tapped Back twice and said 'where is
   the amount?'". Interpretation: "the amount is hard to find". Write both, label which is which, and let
   the reader disagree.
3. **Count participants, not mentions.** One talkative person who raised it five times is one.
4. **Look for what disconfirms.** For each hypothesis, find the participants who do not fit it and report
   them first. A pattern with no exception deserves a second look at who you asked.
5. **Do not turn a quote into a statistic**, and do not turn a statistic into a cause. A tally says how
   many; the interviews suggest why.
6. **Quote exactly** in the participant's own words and language. A translation goes beside it, outside
   the quote marks. Never tidy their grammar.
7. **Verdict against the threshold set before the data.** Supported, refuted, mixed, or inconclusive.
   Inconclusive is honest: too few people, a split audience, a broken question. It is not a failure of
   the study; a false "supported" is.
8. **A finding that changes a job or a rule is a proposal**, with the evidence attached, not a decision.

## 18 · Synthesis

Synthesis turns what you saw into what to do. It is where a study is most easily bent toward what the team
wanted, so each step leaves a trail.

**Observation versus interpretation.** An **observation** is what happened or was said, specific enough
that someone else would have written it down too: "P02 opened Payment, looked at it for 12 seconds, then
went Back". An **interpretation** says what it means: "the total is hidden". Keep them in separate
fields. Interpret only after observing, and let a second reader disagree.

**Every observation cites evidence.** A session event (its index), a time into the session or its
recording, or a verbatim quote from a transcript or notes. The tool refuses an observation whose evidence
is missing or dropped, whose time is outside the session, or whose quote is not in the file word for
word. An observation with no evidence is a belief.

**Tagging.** Give each observation one or two short, lowercase tags that name the **thing**, not the
verdict (`total-hidden`, `cash-unclear`, not `bad`). Use the same tag for the same thing across
participants. Tags are for finding, not for evidence.

**Affinity by participant count.** The tool counts, per tag, observations and **distinct participants**,
and the tasks it appears in. Read participants, not observations: the same person hitting the same snag five
times is one person. Seven tags on one participant are an individual story; a tag across four of five is
a pattern.

**Themes.** A theme groups related tags into a statement of what is going on and why it matters ("People
look for the total before they commit"). It is an insight, written after the counts, and it names its tags.
A theme with a single participant behind it is a hunch.

**Usability issues and severity.** An issue is a specific problem on a specific task and screen, with its
observations and a recommendation. Rate it on Nielsen's 0 to 4 scale, which weighs three things:
**frequency** (how many people hit it), **impact** (how bad it is when they do) and **persistence** (whether
people learn to avoid it, or hit it every time).

| Severity | Name | Meaning |
|---|---|---|
| 0 | Not a problem | You do not consider it a usability problem |
| 1 | Cosmetic | Fix only if there is time |
| 2 | Minor | Low priority |
| 3 | Major | Important to fix; high priority |
| 4 | Catastrophe | Imperative to fix before release |

You propose the severity; the user approves it at G-INSIGHT. **The tool computes frequency (participants
affected out of those tested) and priority (severity times frequency)**; do not type either. Rank the
report by priority, so a severity 4 seen by one person does not outrank a severity 3 seen by four. A
severity 3 or 4 that rests on one participant is flagged: it needs a second look, not a dismissal.

**Disconfirming evidence first.** For each theme and issue, look for the participants who did not have
it and say so. If the design worked for three people and failed for two, report both groups and what
differed between them (experience, role, device).

**One participant is not a pattern.** One person who could not find a button is one person. Write it as
that, and look for it in the next session. Do not let a loud observer, a CEO's pet theory or one vivid
clip decide a finding.

## 19 · Reporting

**Who reads it, and what they do with it.** Write for a person who was not in the room and has ten
minutes: a designer who needs the issues, a product owner who needs the decision, an engineer who needs the
screen and the behaviour. Not for the team that ran it.

**Lead with the decisions and the top issues.** The first page answers: what did we set out to decide,
what did we find, what do we recommend. Give the top three issues by priority, the verdict against each
hypothesis, and what changes next. Method, participants and detail follow.

**Every claim is traceable.** A finding cites the participants and the evidence it rests on (a quote with
its participant and evidence id, a number from the analysis, an issue with its observations). If a reader
cannot find where a statement came from, they should not trust it.

**Show numbers with their intervals.** A rate has its interval and its n; a time has its interval; a score
has its grade and its n. "4 of 5" before any percentage. A chart without its whiskers overclaims.

**State limitations.** Who you reached and how, the n against the target and the word "directional" where
it applies, assisted successes, sessions without recording, the prototype's gaps (what was not real),
consent gaps, and what you did not test. A limitation is what lets a reader weigh the result; it is not an
apology. The tool adds the automatic ones; you add the rest.

**Recommendations are routed and sized.** Each recommendation names the issues behind it and where it goes:
clarify (a job or rule needs rethinking), explore (the design needs alternatives), build (a clear fix), or
none (record and watch). A recommendation without an issue behind it is an opinion; remove it. A verdict is
a proposal, not an edit to the project (§17).

**Do not write the numbers into the narrative by hand.** Write what they mean, and cite them from the
analysis. If a figure you want is not in the analysis, the tool has not measured it.

**The report is reviewed at G-INSIGHT.** The user reads the verdicts, the issue severities, the quotes and
the exact text that will enter the project's insights, against the evidence, and approves, changes or
refuses. A draft report says it is a draft until then. Silence is not approval, and a change after approval
re-opens the gate (`canon.md` § *Research evidence*).
