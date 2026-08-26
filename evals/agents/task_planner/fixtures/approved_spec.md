# Spec (approved) — LEX-2101: Reschedule a booked lesson

## User stories
- As a student, I want to reschedule a booked lesson from the lesson card, so that I do
  not have to cancel and re-book.

## Acceptance criteria (EARS)
- WHEN a booked lesson starts more than 12 hours from now THE SYSTEM SHALL show a
  "Reschedule" action on its lesson card.
- WHEN the student picks a new slot THE SYSTEM SHALL send the tutor a confirmation
  request and keep the original lesson unchanged until the tutor confirms.
- WHEN a lesson has already been rescheduled twice THE SYSTEM SHALL hide the action.
