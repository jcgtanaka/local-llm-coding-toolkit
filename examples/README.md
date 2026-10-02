# Worked example: count ERROR lines in a large log

One generic offload from start to finish. The input is large (a log with
tens of thousands of lines) and the output is small (a short list), which is
the shape this pattern is for.

## 1. The delegation prompt

The thinker writes this into `prompt.txt`, followed by the log contents:

```
You are a precise extraction tool. Below is an application log.
Task: find every line containing the level ERROR. Group them by the error
message text after the level (ignore timestamps and ids), and output one
line per distinct message in the form:

<count> | <message>

Sort by count, highest first. Output only those lines, nothing else.
If there are no ERROR lines, output exactly: NONE

LOG START
<paste or append the log here>
LOG END
```

Build the file (any shell; here the log is `app.log`):

```
cat prompt-header.txt app.log > prompt.txt
```

On Windows PowerShell use `Get-Content prompt-header.txt, app.log | Set-Content -Encoding utf8 prompt.txt`.

## 2. The call

```
python3 .claude/skills/local-model-offload/ask_local.py --model <model-name> --predict 400 --file prompt.txt
```

(Or `python3 path/to/ask_local.py ...` wherever you keep the script. The
model needs an entry in `MODEL_CTX`, or pass `--num-ctx`.)

## 3. Sample output (illustrative only)

The numbers below are made up to show the shape. Your values will differ.

```json
{
  "response": "212 | Connection timeout to db-primary\n37 | Failed to parse payload\n3 | Disk quota exceeded",
  "prompt_tokens": 6890,
  "gen_tokens": 42,
  "prompt_tok_s": 1450.2,
  "gen_tok_s": 61.5,
  "num_ctx": 8192,
  "truncated": false,
  "truncation_status": "ok",
  "done_reason": "stop",
  "cut_by_predict": false
}
```

## 4. Verification checklist applied

Do these before using the result:

1. Exit code is `0` and `truncated` is `false`. (Exit `4` would mean the log
   did not fit the window: split the log and run it in parts.)
2. `cut_by_predict` is `false`, so the list was not cut off at `--predict`.
3. Independently count: run `grep -c "ERROR" app.log` (or
   `Select-String -SimpleMatch ERROR app.log | Measure-Object` on Windows)
   and check the total equals the sum of the counts (212 + 37 + 3 = 252).
4. Spot-check one or two groups: search the log for the top message and
   confirm its count and exact wording.
5. Check nothing was invented: every message in the answer must appear in
   the log.
6. If any check fails, discard the output and do the task directly. Do not
   patch a failed local answer by hand.
