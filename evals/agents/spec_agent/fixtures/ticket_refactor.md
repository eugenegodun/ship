Key: LEX-2102
Summary: Migrate the billing module from moment.js to date-fns
Description:
Tech-debt ticket. Replace all moment.js usage inside `billing/` with date-fns and remove
the moment dependency from that package. No user-facing behavior may change: invoice
dates, proration math, timezone handling for receipts, and the renewal-date display all
stay exactly as they are today. QA note: renewal reminders must keep firing 72 hours
before renewal, in the subscriber's local timezone.
