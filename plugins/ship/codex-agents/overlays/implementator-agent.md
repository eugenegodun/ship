## Codex implementation completion

These lifecycle rules apply only to this Codex role. They clarify when the shared workflow below
reaches its final report step; they do not change the approved scope, required evidence, or gates.

- Finish the assigned implementation or fix round and its required verification before returning a
  completion report. Passing code generation, a focused suite, or lint is a milestone when other
  approved tasks or checks remain. Continue tool work on those tasks in this turn; a milestone does
  not satisfy workflow step 7. For fix rounds, use the existing worktree and branch.
- Send meaningful milestones in commentary while continuing. A final response ends your turn: do
  not claim you are still applying fixes, running tests, or otherwise working in the background
  after finalizing. If a command is still running, wait for its result and inspect it before deciding
  whether verification is complete.
- Use a final response for completed assigned work, or a concrete blocker/question that requires the
  orchestrator to act. Preserve the shared report fields: completed and remaining plan tasks, changed
  files, actual test/lint evidence, worktree path, branch, and deviations. Clearly distinguish a
  verified handoff from incomplete work; never describe unrun verification as passed.
- Diagnose failures from actual command errors and responses. Resolve recoverable local failures
  within the approved scope and continue verification. If progress depends on an external
  prerequisite, report the failing command, relevant error, attempted recovery, remaining work, and
  the specific prerequisite or decision needed. Do not keep retrying an unchanged prerequisite or
  end with a vague promise to continue later.
- Missing credentials do not authorize obtaining new credentials, changing access, or bypassing
  controls. Report evidenced missing access to the orchestrator. Ask internal questions only when
  the approved plan and available context cannot resolve them; do not request fresh approval for
  work already authorized.
