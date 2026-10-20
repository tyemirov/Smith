# Email Cleanup

Email Cleanup helps you review a crowded Gmail mailbox and apply a defined cleanup policy.
It protects useful records and active conversations during bulk operations.

## Problem

A mailbox can mix newsletters, expired notices, important records, and messages that need a reply.
Broad deletion rules can remove useful mail with the unwanted messages.

## Method

1. Examine the available Gmail tools and inspect representative messages.
2. Define the mailbox scope, retention rules, and protected messages.
3. Classify messages before selecting label or Trash operations.
4. Preview the complete action set and obtain confirmation for mailbox changes.
5. Apply the approved rules and report the results.

Protected messages include starred mail, user labels, important records, and recent human conversations.
Uncertain messages remain available for review.
Archive operations require an explicit user choice.

## Install and use

Use the [collection installation guide](https://github.com/tyemirov/Smith#local-installation).
To install this skill alone, run this command from the collection root:

```bash
./install-skills --skill email-cleanup
```

Connect Gmail with search and read access.
Label and Trash operations also require the corresponding connector tools.
With read access alone, the skill supplies search queries and an action plan.

Select `tyemirov:Email Cleanup` in the Codex plugin, or use `/email-cleanup` in Claude Code.

## Example

```text
Use Email Cleanup to review newsletters older than 180 days.
Protect starred mail, my labels, financial records, and active conversations.
Show a preview of the proposed label and Trash operations for confirmation.
```

The result identifies message groups, sample evidence, exclusions, and proposed actions.
After confirmation, the skill reports completed changes and unresolved messages.

Read [SKILL.md](SKILL.md) for the retention framework and complete workflow.
