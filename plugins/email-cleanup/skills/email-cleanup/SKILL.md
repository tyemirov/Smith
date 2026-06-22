---
name: email-cleanup
description: "Use when the user wants to clean up Gmail, reduce inbox volume, reach inbox zero, sort or delete old mail, decide what to keep, or identify safe bulk cleanup patterns. Audit the mailbox with a protection-first retention framework, using Gmail connector tools such as `_search_emails`, `_batch_read_email`, `_search_email_ids`, `_list_labels`, and when available `_delete_emails`, `_bulk_label_matching_emails`, `_apply_labels_to_emails`, and `_create_label`."
---

# Email Cleanup

## When to use
- Clean up a crowded Gmail inbox or long-neglected account.
- Decide which mail to keep, sort, trash, or ignore.
- Find safe bulk cleanup patterns by sender, subject family, or time window.
- Reduce recurring mail volume or identify duplicate subscriptions across addresses.

## Tool map
- Reconnaissance: `_list_labels`, `_search_emails`, `_search_email_ids`
- Reading: `_batch_read_email`
- Actions when available: `_delete_emails`, `_bulk_label_matching_emails`, `_apply_labels_to_emails`, `_create_label`

If only search and read tools are available, analyze the mailbox and give the user exact Gmail search queries plus a conservative action plan. Check capabilities first; do not assume the connector is read-only.

## Safety model
- `_delete_emails` moves messages to Gmail Trash. Treat it as reversible cleanup, not permanent deletion.
- Require explicit user confirmation before any trash or label mutation.
- Default uncertain cases to `sort` or `leave alone`, not `trash`.
- Treat Gmail system labels such as `IMPORTANT`, `CATEGORY_PERSONAL`, and `CATEGORY_UPDATES` as hints only. They are noisy and should not drive decisions alone.

When the user asks for automation, do not fall back to thread-by-thread handholding. Compile a mailbox policy, show the user the policy in a concise preview, and execute the whole pass after a single confirmation unless the user asked for an even stricter review loop.

Unless the user explicitly opts into Gmail archive semantics, do not archive mail. The normal outcomes are:
- keep in inbox
- sort with labels or categories
- delete

## Protection overlay
Build a protected set before any bulk action. Exclude these from bulk searches unless the user explicitly says otherwise:
- Starred mail and mail with user-created labels
- Direct human conversations with recent back-and-forth
- Government, tax, banking, insurance, medical, legal, property, immigration, school-admin, and travel threads that may still matter
- Account recovery, security alerts, receipts with meaningful financial or warranty value
- User-named protected senders, domains, labels, or topics

If the user does not provide a protected list, assume a conservative one from mailbox samples and call it out.

## Composability contract
When the user wants automation, optimize for composability rather than ad hoc one-off passes.

The desired properties are:
- `Composable`: `GTD Inbox` and `Historical Backfill` can run in either order without hiding or invalidating each other, as long as both use non-destructive mutation policies.
- `Idempotent`: rerunning the same program should mostly be a no-op after the first pass.
- `Mostly lossless`: classification and sorting passes preserve the underlying mail corpus. Only an explicit destructive phase shrinks it.
- `Reversible by default`: prefer labels and sorting over trash unless the user explicitly chooses a dead-mail purge.

Achieve this by separating classification from mutation:
- Programs first classify mail into stable namespaces.
- A resolver then maps those classes to Gmail actions.
- Programs may add or refresh their own classifications, but should not remove other programs' classifications.
- Trash is a separate destructive phase, not the default behavior of ordinary programs.
- Archive is disabled by default and must not be used as a substitute for sorting.

Treat these namespaces as conceptual classes first. Materialize them as Gmail labels only when they materially help staged execution or retrieval. Do not create an ornate label tree just to mirror the internal model.

## Axes
Define every automated pass on three axes:
- `Scope`: which subset of the mailbox is in play
- `Classifier`: which lens is being applied to that subset
- `Mutation`: what Gmail action follows from the resulting classes

### Scope axis
Use one or more of these scopes:
- `scope/inbox`: `in:inbox -in:trash -in:spam`
- `scope/backlog`: `in:anywhere -in:trash -in:spam` with a stated age or historical horizon
- `scope/sender-family`: sender-family slices such as newsletters, digests, promotions, reminders, and repetitive transactional mail
- `scope/duplicate-alias`: messages duplicated across multiple recipient aliases
- `scope/records`: durable records such as finance, travel, tax, housing, legal, medical, school, and security mail

### Classifier axis
Use stable classifier namespaces:
- `wf/*`: workflow state for inbox management
  - `wf/action`
  - `wf/waiting`
  - `wf/reference`
- `sem/*`: semantic retention state
  - `sem/retain`
  - `sem/reference`
  - `sem/dead`
- `src/*`: sender-family or source characteristics
  - `src/newsletter`
  - `src/digest`
  - `src/promotion`
  - `src/reminder`
  - `src/duplicate`
- `protect/*`: protected classes that block broad destructive rules
  - `protect/starred`
  - `protect/user-labeled`
  - `protect/finance`
  - `protect/school`
  - `protect/housing`
  - `protect/travel`
  - `protect/legal`
  - `protect/medical`
  - `protect/security`
  - `protect/recent-human`
- `dup/*`: canonical-copy state for alias dedupe
  - `dup/canonical`
  - `dup/redundant`

### Mutation axis
Choose mutation as a separate resolver, not as part of the classifier:
- `label-only`: classify without changing Gmail placement
- `sort`: assign stable labels or categories without archiving
- `sort-first`: sort normal reference mail, reserve trash only for explicitly redundant or explicitly purged mail
- `quarantine`: label ambiguous mail `cleanup/review` and leave placement unchanged
- `trash`: destructive phase for mail already classified as safely discardable

Gmail caveat:
- Gmail does not offer a non-destructive "move out of inbox without archive" primitive.
- If archive is forbidden, `sort` means labels and categories, not removal from `INBOX`.
- Therefore, literal inbox-zero on Gmail is only possible with deletion or with an explicit override that allows archive semantics.

## Resolver rules
Use these precedence rules when multiple classifiers apply:
- Any `protect/*` class overrides broad sort or trash rules unless the user explicitly broadens scope.
- `dup/redundant` can be trashed only if a `dup/canonical` copy exists and matches the same notification family.
- `wf/action` and `wf/waiting` stay in the inbox.
- `wf/reference`, `sem/reference`, and `sem/retain` should usually sort, not trash.
- `sem/dead` sorts by default and only trashes under an explicit dead-mail purge policy.

## Named programs
Named programs are bundles over the three axes, not separate incompatible universes:
- `GTD Inbox` = `scope/inbox` + `wf/*` classifier + non-destructive mutation
- `Historical Backfill` = `scope/backlog` + `sem/*` classifier + non-destructive mutation
- `Noise Reduction` = `scope/sender-family` + `src/*` and `sem/*` classifiers + usually `sort-first`
- `Duplicate/Alias Consolidation` = `scope/duplicate-alias` + `dup/*` classifier + `trash` or `sort-first` for redundant copies only
- `Records Preservation` = `scope/records` + `protect/*` and `sem/*` classifiers + `sort`
- `Dead Mail Sweep` = sender-family or backlog scope + `sem/dead` classifier + explicit `trash`

Programs can be combined when they share the same composability contract, for example:
- `GTD Inbox` + `Records Preservation`
- `Historical Backfill` + `Noise Reduction`
- `Historical Backfill` + `Duplicate/Alias Consolidation`

`Dead Mail Sweep` is the exception: it is intentionally destructive and is not isomorphic with later sort-only passes.

## Policy inputs
For an automated pass, define these policy inputs before acting:
- `Program bundle`: one or more named programs
- `Time horizon`: current inbox, last 30/90/180 days, or full historical backlog
- `Mutation resolver`: what to do with `wf/reference`, `sem/reference`, `sem/dead`, and `dup/redundant`
- `Protected set`: extra senders, domains, labels, or topics beyond the default overlay
- `Alias policy`: which address is canonical when duplicate notifications hit multiple aliases
- `Review sink`: whether ambiguous mail should be left alone or labeled `cleanup/review`

Do not ask the user to approve each sender family one by one if they have already asked for automation. Ask only for the program bundle and mutation resolver when needed, then execute that policy in bulk.

## Retention classes
Every reviewed thread gets one semantic class:
- `Retain`: long-term records or meaningful personal correspondence
- `Action`: live open loop, real deadline, missing reply, unresolved dispute, or current coordination
- `Reference`: useful for lookup in the next 6-12 months, but not worth inbox space
- `Dead`: broadcast, expired, concluded, or low-value mail that no longer earns retention

Execution mode is separate from semantic class:
- `Single-thread review`
- `Bulk sort by pattern`
- `Bulk trash by pattern`
- `Label then sort`
- `Manual Gmail query fallback`

## Semantic scoring
For each sender family or thread, evaluate four axes:
- `Human vs broadcast`
- `Actionable vs FYI`
- `Durable vs ephemeral`
- `Active vs expired`

Use this to route mail:
- Broadcast + FYI + ephemeral + expired => usually `Dead`
- Human + actionable + active => usually `Action`
- Transactional + durable enough to search later => usually `Reference`
- Legal, financial, or sentimental significance => `Retain`

Do not use the shortcut "recent human mail with no reply always means action." A real human message can still be social, informational, concluded, or dead.

## Autonomy

Execute the full workflow without pausing for user confirmation between steps.
The validation gates defined in this workflow are the only stopping points.
Do not ask "should I proceed?" or "should I continue?" at intermediate steps.
Report the final outcome when the workflow completes or a gate stops it.

## Workflow
1. Capability check
   - Confirm Gmail access with `_list_labels` or `_search_emails`.
   - Note whether action tools are present.
2. Set the policy
   - Choose the program bundle.
   - Set the time horizon.
   - Choose the mutation resolver for `wf/reference`, `sem/reference`, `sem/dead`, and `dup/redundant`.
   - Record any user-specified protected senders, domains, labels, or topics.
   - Record alias handling for duplicate notifications.
3. Build the protected overlay
   - Create the default `protect/*` set from starred, user-labeled, durable-domain, and recent-human signals.
   - Add any user-specified protected senders, domains, labels, or topics.
4. Reconnaissance
   - Start with counts and representative samples, not immediate cleanup.
   - Use queries such as `in:inbox older_than:1y`, `is:unread older_than:30d`, `has:unsubscribe older_than:180d`, and targeted `from:` searches for dominant senders.
   - Identify sender families, not just message counts: newsletters, school ops, transactional, human coordination, marketing, security, travel, and similar groups.
5. Compile classification rules
   - Convert sender families and durable domains into 3-8 classification rules, not a long list of one-off actions.
   - For each rule, define scope, classifier namespace, query, exclusions, and expected resolver outcome.
   - Ensure the rules match the chosen program bundle. `GTD Inbox` should primarily classify `wf/*`; `Historical Backfill` should primarily classify `sem/*`; `Duplicate/Alias Consolidation` should focus on `dup/*`.
   - Sample 1-3 messages per rule to validate the class, then keep moving.
6. Resolve mutations
   - Apply the mutation resolver to the classified rules.
   - Keep destructive behavior isolated. If the user did not choose a destructive phase, `sem/dead` should sort or quarantine rather than trash.
   - Present the resulting bulk rules as a concise preview and ask for one confirmation for the whole pass.
7. Check duplicate subscriptions
   - Look for the same sender delivering to multiple recipient addresses or aliases.
   - Recommend unsubscribing one address or filtering duplicates when it reduces noise without losing coverage.
8. Execute after confirmation
   - Prefer labels, categories, and other sorting actions over archive.
   - Use `_apply_labels_to_emails`, `_batch_modify_email`, or `_bulk_label_matching_emails` for sorting passes where possible.
   - Batch trash sets found via IDs with `_search_email_ids` followed by `_delete_emails` only when the delete policy permits it.
   - For ambiguous but probably low-value mail, prefer label-only to `cleanup/review` rather than blocking the whole automated pass.
   - If the connector cannot safely mutate the whole set server-side, give the user the exact Gmail search query to run manually.
9. Triage the remainder
   - Only after the bulk pass, inspect the leftover inbox or unread backlog.
   - Review inbox threads in batches with `_search_emails`.
   - Escalate to `_batch_read_email` only for ambiguous threads or when the snippet is insufficient.
   - Present the batch grouped by `Action`, `Reference`, `Retain`, and `Dead`.
10. Summarize
   - Report what changed, what remains, and the next safest pass.

## Default automated framework
When the user wants the skill to "just do it," use this default framework unless they specify a different policy:

- Program bundle: `Historical Backfill` + `Noise Reduction` + `Duplicate/Alias Consolidation`
- Time horizon: historical backlog plus stale inbox broadcast mail
- Mutation resolver:
  - `wf/action` and `wf/waiting` stay in inbox
  - `wf/reference`, `sem/reference`, and `sem/retain` sort
  - `sem/dead` sorts by default
  - `dup/redundant` trashes only when a `dup/canonical` copy exists
- Protected set:
  - starred mail
  - user-labeled mail
  - finance, tax, legal, medical, school-admin, housing, travel, government, and security threads
  - recent human conversations
- Alias policy: keep one canonical copy per duplicate notification family and trash the duplicate copy sent to the secondary alias
- Review sink: label ambiguous stale mail as `cleanup/review` rather than blocking the pass

Default bulk rules for that framework:
- Classify newsletters, digests, and Substack mail older than 14-30 days as `src/newsletter` + `sem/dead`, then sort them unless protected
- Classify stale promotions older than 30 days as `src/promotion` + `sem/dead`, then sort them by default and trash them only under an explicit dead-mail sweep
- Classify expired shipment, event, and reminder mail as `src/reminder` or `src/digest` + `sem/dead`, then sort them after the event window closes
- Classify duplicate notifications sent to multiple aliases as `src/duplicate` + `dup/*`, then trash only the `dup/redundant` copy after choosing the canonical recipient
- Classify finance, school, travel, housing, medical, legal, and security mail into `protect/*` and keep them out of broad destructive rules

The framework should optimize for "few approvals, large safe passes" rather than "perfect classification before any action."

## Safe bulk patterns
Usually safe to sort after sampling:
- Newsletters, digests, and Substack mail older than 90-180 days
- School newsletters and recap mail older than a term or school year, if not direct coordination
- Delivery, shipment, flight status, and calendar reminder mail after the event is over
- Marketing and promotions older than 90-180 days
- Repeated system notifications that do not affect account access or billing

Usually safe to trash after sampling:
- Promotions, coupons, and expired deal mail
- Redundant alerts that are clearly time-bound and already stale
- Obvious duplicate notifications to multiple addresses
- Old broadcast mail from senders the user no longer uses

Do not bulk trash coarse queries like these without sampling and exclusions:
- `from:noreply older_than:1y`
- `subject:"password reset" older_than:3m`
- `has:nouserlabels older_than:3y -is:starred`

Those queries catch too much security, billing, government, and unlabeled human mail.

## Labels
Use labels sparingly. The goal is less mail, not a more ornate filing system.
- Create a label only when it materially helps retrieval or staged cleanup.
- Good examples: `cleanup/review`, `reference/school`, `reference/travel`
- Avoid labeling bulk mail unless it is part of a temporary cleanup pass.

## Output format
Prefer concise tables or flat lists over long explanations. For each proposed action batch, include:
- Scope
- Classifier
- Query or sender family
- Sample evidence
- Semantic class
- Proposed action: sort, trash, label, or review
- Risk note or exclusion set

When operating in automation-first mode, lead with:
- `Program bundle`
- `Mutation resolver`
- `Protected`
- `Bulk rules`
- `Apply now`

Ask for one approval on the full pass, not sender-by-sender approvals.

For inbox triage batches, group by verdict:
- `Action`
- `Reference`
- `Retain`
- `Dead`

For `Action`, state the open loop. For `Dead`, state why it is safe. For `Reference`, give a rough expiry horizon when obvious.

## Maintenance
After a cleanup pass, recommend only lightweight habits:
- Weekly or monthly review of new bulk senders
- Sort reference mail consistently
- Re-run the safest bulk patterns before doing any deeper review
