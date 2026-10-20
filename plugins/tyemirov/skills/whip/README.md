# Whip

Whip helps an editing agent revise a document while it preserves approved facts, decisions, qualifications, and citations.
Use it with `$whip`.
The complete agent instructions are in [SKILL.md](SKILL.md).

## The problem

A document collects requirements across many revisions.
A request to shorten or reorganize it can produce clear prose that silently changes earlier decisions.
The requested addition appears, but a condition, exception, or supporting argument disappears.

A text comparison shows changed words.
It does not establish whether the revised document preserves the original meaning.
For example, “may proceed after approval” and “will proceed” describe different commitments.
Both can appear reasonable when read without the baseline.

Whip treats document revision as a change that requires evidence.
It combines mechanical checks with a separate review of meaning.
The result is a candidate with traceable changes and an explicit acceptance status.

## Our methodology

1. **Freeze the baselines.** Keep the last approved version and an exact copy from the start of the session.
   Record their source locations and version identifiers.
   If approval is unknown, mark the session copy as provisional.
2. **Record the requirements.** Build a fact-and-decision ledger with stable IDs, source quotes, and locations.
   Include tables, captions, footnotes, exceptions, and uncertainty.
3. **Define the change.** Record the changes that the user requests.
   Map each source unit to its destination or an explicitly authorized deletion.
4. **Edit the candidate.** Keep the candidate separate from the baselines.
   Use native document operations where available to preserve formatting and metadata.
5. **Run mechanical checks.** Check protected sections, required text, baseline fingerprints, and changes to numbers.
   Record and examine each warning.
6. **Review meaning independently.** Give a separate reviewer the complete sources, candidate, ledger, change plan, mapping, and mechanical report.
   The reviewer first reconstructs the baseline claims to detect gaps in the editor’s ledger.
   It checks preserved meaning, new claims, contradictions, and citation support.
7. **Repair and repeat.** Let the editor repair the candidate.
   After each repair, repeat the checks and independent review.
8. **Accept with evidence.** Accept only after the required checks pass and material uncertainties are resolved.
   Keep the baselines and review artifacts.

For an isolated correction, Whip uses a smaller process: identify the affected units, edit them, and compare the surrounding content.
Changes to shared definitions, numbers, conclusions, or several sections require the full process.

## Practical example

Suppose an approved proposal contains these statements:

> The annual target is $400,000.
> Initial customers are enterprise teams.
> The pilot starts only after the security review passes.

The user requests: “Shorten the architecture section and move it after the rollout plan.”
This request permits a structural change.
The target, customer group, and pilot condition remain protected.

The editor records this small ledger:

| ID | Requirement | Validation |
| --- | --- | --- |
| F-001 | Annual target: $400,000 | Required text and meaning |
| D-001 | Initial customers: enterprise teams | Independent review of meaning |
| R-001 | Pilot requires a passed security review | Independent review of the condition |

A candidate changes the pilot statement to “The pilot starts alongside the security review.”
It still mentions both the pilot and the review.
But it removes the prerequisite.
The independent reviewer reports a contradiction and quotes both statements.
The editor restores the condition and submits the revised candidate for another review.

If the candidate changes `$400,000` to `$300,000`, a required-text check can also detect the regression.
The two checks address different failure types.

## Use the skill

### Start a revision

Make the complete `whip` folder available in your host’s skill directory.
Keep its scripts, references, assets, and reviewer configuration together.
In a repository checkout, you can also direct an agent to read `whip/SKILL.md` explicitly.

Example request:

```text
Use $whip to revise this document.
Revise proposal.md using approved-proposal.md as the approved baseline.
Shorten the architecture section and move it after the rollout plan.
Preserve all other facts, decisions, conditions, and citations.
Save a separate candidate and the review artifacts.
```

Provide the document, its approved baseline if available, and the requested changes.
For native documents, provide their accessible source links and version identifiers.

### Set up independent review

From the public collection checkout, install all skills and the reviewer:

```bash
uv run --script install-skills
```

Run this command from the `agentSkills` checkout.
The public repository includes the installer and its required dependencies.
It preserves existing skill links, unrelated skills, and controller model settings.
Identical reviewer files remain unchanged.
A conflicting reviewer stops installation before profile changes.
Use `--dry-run` to preview the operations or `--check` to verify the installation.

For a standalone or plugin installation, copy [whip_reviewer.toml](codex/agents/whip_reviewer.toml) into `.codex/agents/` in the target project.
For personal installation, use `~/.codex/agents/`.
The plugin bundle includes the reviewer file but does not register it in that directory.

After the editor prepares the candidate and mechanical report, ask it to delegate to `whip_reviewer`.
The reviewer reads the artifacts and returns findings.
The parent agent owns repairs and saves the report.
See the [reviewer protocol](references/reviewer-protocol.md) for the complete input and JSON contracts.

If the host supports unnamed subagents, use a separate subagent with the same protocol.
If separate review is unavailable, the independent review status remains `PENDING`.

### Run the checks for Markdown or plain text

The scripts use `uv`, Python 3.10 or later, and the standard library.
From the `whip` directory, run these commands with paths to your revision artifacts.

```bash
uv run --script scripts/check_revision.py \
  --approved approved.md --session session.md --candidate candidate.md \
  --ledger ledger.json --report mechanical-report.json
```

Prepare the ledger from [ledger.example.json](assets/ledger.example.json).
Replace the example facts and paths with evidence from your document.
Use the [change plan](assets/change-plan.template.md) to record the authorized scope and source mapping.

After independent review, save its JSON response as `reviewer-report.json`.
Then run:

```bash
uv run --script scripts/gate_review.py \
  --approved approved.md --session session.md --candidate candidate.md \
  --ledger ledger.json --mechanical mechanical-report.json \
  --review reviewer-report.json --report release-gate.json
```

The second script checks report structure, fingerprints, coverage, quoted text, authorization IDs, and warning dispositions.
Its `PASS` confirms these checks.
The reviewer must still assess meaning and citation support.
For native documents, use native comparison tools and review the complete document.

## Results and verification

A substantial revision produces the candidate, immutable baselines, ledger, change plan, source mapping, mechanical report, and independent review report.
Plain-text workflows also produce the release-gate result.
The final status distinguishes verified work, a candidate pending review, and blocked work.

Run the included tests from the `whip` directory:

```bash
python -B -m unittest discover -s tests -v
```

The tests cover fact loss, changed baselines, ambiguous headings, numeric changes, incomplete reviews, invented quotes, and stale candidates.
They test the scripts’ behavior.
They do not prove that an individual document preserves its meaning.
