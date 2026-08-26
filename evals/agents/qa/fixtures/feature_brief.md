Feature under test (ticket LEX-2101): students can reschedule a booked lesson from the
lesson card. Reschedule is shown only for lessons >12h away and at most twice per lesson;
picking a slot sends the tutor a confirmation request (lesson unchanged until confirmed).
The card lives at /my-lessons; the flow is gated by the Waffle flag
`exp_lesson_reschedule_v1`. The PR does not exist yet — you were launched in parallel with
the review/PR stage. Author the plan from this description; do not run `gh pr view` or
infer a branch. I'll hand you the PR ref when I resume you for Phase B.
