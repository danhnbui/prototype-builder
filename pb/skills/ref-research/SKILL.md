---
name: ref-research
description: The method for validating what a project is unsure about with real people in Product Builder — choosing survey or interview, turning a job's when/want/so and a flow's path into past-behaviour questions and prototype tasks, the question-writing rules and the bias list, building a screener, a scale or an interview guide, honest sample-size rules of thumb, and reading results without fooling yourself. Use when writing a study's hypotheses and instrument and when synthesizing its evidence — loaded by /pb:research §1. Not for the tool's commands and gates (/pb:research), usability heuristics on a design (think-layout), or scoring design options (ref-design-compare).
user-invocable: false
---

# ref-research

A study is sound when it could have told you that you were wrong. Most do not: the questions invite the
answer the author wants, the sample is whoever was easy to reach, and the write-up counts the quotes that
agree. This skill is the discipline that stops that. The tool checks structure and arithmetic; **nothing
here is checked for you**, so read §4 and §7 twice.

Provenance: Portigal, *Interviewing Users* (interviews); Fitzpatrick, *The Mom Test* (asking about past
behaviour, not opinions of your idea); Krug, *Rocket Surgery Made Easy* (small, repeated usability
sessions); Krosnick & Presser, "Question and Questionnaire Design" (*Handbook of Survey Research*, 2nd ed.;
wording, order, response scales); Christensen and Ulwick on jobs-to-be-done (a job is a situation and an
outcome). Sample sizes in §6 are rules of thumb stated as such, not results from those books.

## 1 · Choose the method

| The question | Use | Why |
|---|---|---|
| Why do they do it? How? What goes wrong? What do I not know to ask? | **Interview** | Open, follows the person, finds things you did not think of |
| Can they finish this flow on the prototype? | **Interview with a task** | You watch what they do, not what they say they would do |
| How many? How often? Which of these? | **Survey** | Counts across more people, on something you already understand |
| I am not sure what the options even are | **Interview first** | A survey can only measure the options you listed |

If you can list the answer options without asking anyone, a survey can size them. If you cannot, interview.

## 2 · From jobs and flows to questions

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

## 3 · Past behaviour over opinion

People are poor at predicting what they would do and good at reporting what they did.

| Ask about | Not about |
|---|---|
| the last time it happened | what usually happens, or what they would do |
| what they actually did, in order | what they think of your idea |
| what it cost them (time, money, a workaround) | whether they would pay for it |
| what they use today | what they would switch to |

Compliments, "that would be great" and "I would definitely use that" are not evidence. A specific past
episode, a workaround they built, or something they spent money on is.

## 4 · Writing a question

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
  not meaningful (§5).
- **Social desirability.** People report what looks good. Ask about a specific past episode and make the
  unflattering answer easy ("Many people skip this. Did you last week?" can itself lead, so prefer
  "Last week, how many times did you ...?").
- **Sunk cost of the author.** You built it, so you hear praise and explain away trouble. Write the
  `refutedIf` before you field. In a session, never defend the design or explain it; a user who is
  confused is the data.
- **Naming the feature early.** A question that names the thing under test before the task has told the
  person what to look for. Describe the goal, not the feature.

## 5 · Building the instrument

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
  weren't here?"). Note where they hesitate, go wrong or give up. Agree what success is beforehand.
- **Probes** (write them in advance, use them when needed): "Can you say more?" "What do you mean by
  that?" "Can you show me?" "What did you expect to happen?"
- **Silence.** Wait 5 seconds after an answer. People fill silence with the useful part.
- **Not defending the design.** When they criticise, say "thank you, tell me more". Never explain why it
  is like that.
- **Close**: "Is there anything I did not ask that I should have?" and thank them.
- About 30 to 45 minutes per session; shorter for a single task.

## 6 · Sample size, said honestly

These are rules of thumb, not statistics. They set what you may claim.

- **About 5 interviews per segment** will usually surface most of the usability problems in a flow, and
  that is all they do. They do not tell you how many people have a problem. **Never report a percentage
  from interviews.** Say "3 of 5 participants".
- **More segments, more people.** 5 per segment, not 5 total. A difference between segments needs
  enough in each segment to see it.
- **A survey under about 30 respondents is directional only.** Say "directional" next to every number.
  With a small base, one respondent moves a percentage by several points.
- **Always report n**, per question when it differs, and the number excluded by the screener.
- **A segment-wise comparison needs n per segment**, stated for each group. Do not compare 12 people with 4.
- **Who answered is a limit.** People who answer a survey, or agree to an interview, differ from those who
  do not. Say who you reached and how.
- **One participant is an anecdote.** Say it is, and do not build a verdict on it.

## 7 · Reading results

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

## 8 · Ethics and data

- **Consent first**, in words the person understands: what is recorded, who will see it, how it is
  used, and that they can stop or withdraw at any time. Record that they agreed. No consent, no data.
- **Pseudonyms.** `P01`, `P02`. Never a real name in a transcript, a note, a file name or a quote. Leave
  out or remove names, phones, emails and addresses from what you store.
- **Withdrawal.** If someone withdraws, their data leaves the findings. Do not argue them out of it.
- **Minimal data.** Collect only what the hypotheses need. A column you do not use is a liability.
- **Honest framing.** Do not tell participants the study is about something it is not, and do not
  recruit people who could not freely say no (someone whose manager is watching).
- **Never invent people.** A made-up respondent, however plausible, is not research. Real people, or no
  claim.
