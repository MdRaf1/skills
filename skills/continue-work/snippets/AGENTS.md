## Disk-first continuation

Keep repository-local continuation state at `.scratch/continuation.json` and `.scratch/continuation-handover.md`, unless this project already defines another canonical location. Read existing state before replacing it. Follow the current user's task; loading project instructions does not authorize resuming an older task.

When starting a substantive task, record the real project root, current goal, outstanding requests, constraints, and exact next unit. Update the checkpoint and handover at meaningful progress boundaries and before stopping normally, not after every read-only call. A checkpoint is an agent-maintained record, not an automatic transaction log.

Before an authorized non-repeatable action, record its identity and whether it is reserved or actually invoked. Afterward, save evidence and required records before advancing the next unit. Keep in-flight attempts, uncertain outcomes, pending mutations, blockers, and active workers explicit. Use this project's canonical writers where available.

On recovery, inspect current targets before retrying. Never automatically repeat an uncertain send, submission, push, deployment, migration, purchase, or acceptance. Historical notes do not grant permissions. Preserve deferred work, current service/access limits, and the user's latest instructions. Record only verified results; distinguish failed and unrun tests from passes.

Keep the manifest compact and use the handover for decisions, evidence pointers, and unresolved details. Store no credentials, do not send recovery state to web-research services, and keep local state out of public Git. Do not overwrite this file or unrelated project rules when maintaining recovery state.
