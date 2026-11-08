#!/usr/bin/env python3
"""
research_methods.py — what a researcher decides BEFORE fielding, as data. Stdlib only, pure (no I/O).

  METHOD_CATALOG          the six methods /pb:research can run (runner True) plus the ones it only lists
                          (runner False): what each answers, when it fits, when it does not, a sample-size
                          rule of thumb, typical session minutes, and the numbers the tool computes for it.
  default_checklist(m, mode)   the logistics checklist a new study starts with, as
                          [{"id","text","done":False,"at":None}], ordered the way the work happens.

The rules of thumb are rules of thumb (ref-research §6), not statistics: they say how much a
study may claim, never that a number is proven. Nothing here is a benchmark.
"""

RUNNABLE = ("survey", "interview", "usability", "tree-test", "card-sort", "first-click")

METHOD_CATALOG = [
    {"method": "survey", "kind": "attitudinal", "data": "quant",
     "answers": "How many of a defined group hold a view, have a habit, or run into a problem, and how views differ by segment.",
     "when": "You already know what to ask and need counts; the question can be answered in a few minutes without watching anyone use the product.",
     "n": "Under about 30 respondents is directional only; aim for 30 or more, and per segment if you compare segments.",
     "minutes": "3 to 5", "runner": True,
     "outputs": ["counts and shares per option", "scale means", "standard-metric scores (CES, SEQ, CSAT, NPS, SUS)", "screener drop count"],
     "notFor": "Finding out why something is hard, or what people actually do: people report habits poorly and cannot describe what they have not met."},
    {"method": "interview", "kind": "attitudinal", "data": "qual",
     "answers": "Why people do what they do, in their words: context, goals, workarounds, vocabulary.",
     "when": "You do not yet know the right questions, or you need the reasons behind a pattern you have already seen.",
     "n": "About 5 per segment surfaces most recurring problems; it does not say how many people share one. Report '3 of 5', never a percentage.",
     "minutes": "30 to 45", "runner": True,
     "outputs": ["participants per theme", "verbatim quotes", "hypothesis verdicts from quotes"],
     "notFor": "Measuring how common something is, or settling a design preference by vote."},
    {"method": "usability", "kind": "behavioural", "data": "both",
     "answers": "Can people complete the tasks that matter on this prototype, how long does it take, and where do they stop, hesitate or go wrong?",
     "when": "There is a clickable flow and a clear task for it; you want to find and rank problems before building more.",
     "n": "About 5 participants per segment finds most recurring problems (qualitative). Success rates come with wide intervals below about 20; say 'directional'.",
     "minutes": "30 to 45", "runner": True,
     "outputs": ["task success with adjusted-Wald interval", "time on task (geometric mean and interval)", "lostness against the optimal path",
                 "clicks, dead and rage clicks, errors", "SEQ per task", "SUS with grade", "paths taken"],
     "notFor": "Judging whether people want the product, or comparing two designs for preference. A prototype with no real data is a poor basis for SUS-style verdicts on the whole product."},
    {"method": "tree-test", "kind": "behavioural", "data": "quant",
     "answers": "Can people find where something lives in a text-only menu structure, free of layout and visual design?",
     "when": "You are choosing or changing the information architecture or its labels, before or after a sitemap is drawn.",
     "n": "About 50 participants for stable success and directness figures; 15 to 20 gives a rough read.",
     "minutes": "10 to 15", "runner": True,
     "outputs": ["success rate per task with interval", "directness (no backtracking)", "first-click node", "destinations chosen", "time"],
     "notFor": "Judging a screen layout, or finding out how people group things in their own heads (use a card sort)."},
    {"method": "card-sort", "kind": "attitudinal", "data": "quant",
     "answers": "How people group and name the things in your product, so categories match their mental model.",
     "when": "You are creating or restructuring the grouping of content or features and do not yet trust your own categories.",
     "n": "About 15 participants for a stable similarity picture; fewer than 10 is anecdotal.",
     "minutes": "15 to 25", "runner": True,
     "outputs": ["card-to-card similarity matrix", "average-linkage clusters", "category agreement for closed and hybrid sorts"],
     "notFor": "Testing whether people can find things in a finished structure (use a tree test). More than about 60 cards tires participants."},
    {"method": "first-click", "kind": "behavioural", "data": "quant",
     "answers": "Where do people click first to start a task on this screen, and is that the place that leads to success?",
     "when": "A single screen's layout, labelling or call to action is in question and the first step decides the outcome.",
     "n": "About 30 participants per screen for a stable hit rate.",
     "minutes": "5 to 10", "runner": True,
     "outputs": ["first-click success with interval", "click points", "time to first click"],
     "notFor": "Whole journeys or anything that needs more than one step to judge."},
    {"method": "diary study", "kind": "behavioural", "data": "qual",
     "answers": "What happens over days or weeks in real life: recurring moments, triggers, workarounds, how needs change.",
     "when": "The behaviour is infrequent or spread over time and cannot be watched in one session.",
     "n": "About 8 to 12 participants, because some will drop out.",
     "minutes": "5 a day for 1 to 4 weeks", "runner": False,
     "outputs": [],
     "notFor": "A quick answer: it needs weeks and a diary tool that /pb:research does not provide. Field it elsewhere and import the notes."},
    {"method": "contextual inquiry", "kind": "behavioural", "data": "qual",
     "answers": "How work is really done in its own setting, with the real tools, interruptions and people around it.",
     "when": "The environment shapes the work and you need to see it, not hear about it.",
     "n": "About 5 to 8 visits per segment.",
     "minutes": "60 to 120", "runner": False,
     "outputs": [],
     "notFor": "Testing a specific prototype task, or situations you cannot attend. It needs a site visit and consent from everyone present."},
    {"method": "concept test", "kind": "attitudinal", "data": "both",
     "answers": "Does the idea make sense to the intended audience, and what do they think it is for, before anything is built.",
     "when": "Choosing between early directions, or checking that the value is understood.",
     "n": "About 5 per segment for reactions; about 30 or more if you report shares.",
     "minutes": "15 to 30", "runner": False,
     "outputs": [],
     "notFor": "Predicting demand: stated interest in an idea is a weak signal of later use. Run it as an interview or survey and import the result."},
    {"method": "five-second test", "kind": "attitudinal", "data": "both",
     "answers": "What do people remember and understand from a screen after a brief look: the first impression of purpose and hierarchy.",
     "when": "You want to know what a landing screen or page communicates at a glance.",
     "n": "About 30 participants.",
     "minutes": "2 to 3", "runner": False,
     "outputs": [],
     "notFor": "Whether people can use the screen. It measures recall, not task success. Field it in a tool that hides the image after the time and import the answers."},
    {"method": "A/B preference", "kind": "attitudinal", "data": "quant",
     "answers": "Which of two designs people say they prefer, and for what reasons they give.",
     "when": "Two finished alternatives exist and the team needs a tie-breaker for a low-stakes choice.",
     "n": "About 30 or more per option, more for a small difference.",
     "minutes": "3 to 5", "runner": False,
     "outputs": [],
     "notFor": "Deciding which design performs better: preference and performance often disagree. Test both with tasks (usability) if the choice matters."},
]


def _item(i, text):
    return {"id": i, "text": text, "done": False, "at": None}


def _norm_mode(mode):
    return mode if mode in ("moderated", "unmoderated", "both") else "moderated"


def default_checklist(method, mode):
    """The checklist a study starts with. Same inputs, same list, same order."""
    mode = _norm_mode(mode)
    moderated = mode in ("moderated", "both")
    unmoderated = mode in ("unmoderated", "both")
    session = method in ("usability", "tree-test", "card-sort", "first-click")
    live = moderated if session else (method == "interview")
    out = [_item("plan-approved", "Research plan read and approved by the people who will act on the result")]
    if method in ("survey", "interview", "usability"):
        out.append(_item("screener-ready", "Screener written, and tested against the recruitment channel"))
    out.append(_item("consent-ready", "Consent text agreed, and the way each participant's answer is kept is decided"))
    out.append(_item("withdrawal-agreed", "Withdrawal agreed: who drops a participant's evidence, and how a participant asks"))
    if method == "usability":
        out.append(_item("tasks-checked", "Task wording does not use the labels on screen; success criteria agreed beforehand"))
    elif method == "tree-test":
        out.append(_item("tree-checked", "Tree labels match the live navigation wording; correct answers agreed before launch"))
    elif method == "card-sort":
        out.append(_item("cards-checked", "Card labels are neutral and carry no category names; card count is between 10 and 60"))
    elif method == "first-click":
        out.append(_item("targets-checked", "Target regions checked at the device size participants will use"))
    out.append(_item("incentives-budgeted", "Incentives budgeted, and the way they are paid is decided"))
    if live:
        out.append(_item("note-taker-assigned", "Note-taker assigned, and the note-taking codes agreed"))
        out.append(_item("room-link-ready", "Room or call link ready and tested, with a back-up"))
    out.append(_item("pilot-run", "Pilot run with one person from the audience; wording and timing fixed from it"))
    if session or method == "interview":
        out.append(_item("recording-tested", "If screen or voice recording will be asked for: tested end to end, including the saved file"))
    if session and unmoderated:
        out.append(_item("kit-opened-clean", "Participant kit opened and completed once on a clean machine and browser profile"))
        out.append(_item("return-path-explained", "Instructions for sending the session file back are written and tested"))
    out.append(_item("invites-sent", "Invitations sent, with the time needed and what to expect"))
    out.append(_item("evidence-imported", "Each session imported as evidence, with its hash recorded"))
    return out


def catalog_entry(method):
    """The catalog row for a method, or None."""
    for c in METHOD_CATALOG:
        if c["method"] == method:
            return c
    return None
