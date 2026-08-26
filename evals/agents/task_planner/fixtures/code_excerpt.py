# excerpt: lessons/services/booking.py (fixture — trimmed for the eval)
class BookingService:
    def cancel(self, lesson_id: int, actor: "User") -> None:
        lesson = self.repo.get(lesson_id)
        self._assert_actor_can_modify(lesson, actor)
        lesson.status = "CANCELLED"
        self.repo.save(lesson)
        self.notifications.lesson_cancelled(lesson)

    def book(self, tutor_id: int, student_id: int, slot: "Slot") -> "Lesson":
        if not self.calendar.is_free(tutor_id, slot):
            raise SlotTakenError(slot)
        lesson = Lesson(tutor_id=tutor_id, student_id=student_id, slot=slot, status="BOOKED")
        self.repo.save(lesson)
        self.notifications.lesson_booked(lesson)
        return lesson
