"""Unit tests for adapters/claude-code/ask_local.py (pure logic, no network)."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load_module(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ask = load_module("ask_local", "adapters/claude-code/ask_local.py")


class TruncationRule(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(ask.assess_truncation(500, 2048), "ok")

    def test_margin_is_one_percent_with_floor_of_eight(self):
        self.assertEqual(ask.truncation_margin(2048), 20)
        self.assertEqual(ask.truncation_margin(100), 8)

    def test_exactly_at_margin_is_truncated(self):
        # num_ctx 2048, margin 20 -> threshold 2028
        self.assertEqual(ask.assess_truncation(2028, 2048), "truncated")
        self.assertEqual(ask.assess_truncation(2027, 2048), "ok")

    def test_full_window_is_truncated(self):
        self.assertEqual(ask.assess_truncation(2048, 2048), "truncated")

    def test_zero_or_missing_is_unverified(self):
        self.assertEqual(ask.assess_truncation(0, 2048), "unverified")
        self.assertEqual(ask.assess_truncation(None, 2048), "unverified")


class Preflight(unittest.TestCase):
    def test_refuses_over_ninety_percent(self):
        num_ctx = 1000
        too_big = "x" * int(0.9 * num_ctx * ask.CHARS_PER_TOKEN + 10)
        self.assertTrue(ask.preflight_refuses(too_big, num_ctx))

    def test_allows_small_prompt(self):
        self.assertFalse(ask.preflight_refuses("hello", 1000))


class HostNormalization(unittest.TestCase):
    def test_bare_host_port(self):
        self.assertEqual(ask.normalize_host("myhost:11434"), "http://myhost:11434")

    def test_bare_host_without_port_uses_default_port(self):
        self.assertEqual(ask.normalize_host("myhost"), "http://myhost:11434")

    def test_full_url_kept_and_trailing_slash_removed(self):
        self.assertEqual(ask.normalize_host("https://example.com:8443/"), "https://example.com:8443")

    def test_empty_uses_default(self):
        self.assertEqual(ask.normalize_host(""), "http://localhost:11434")
        self.assertEqual(ask.normalize_host(None), "http://localhost:11434")

    def test_env_used_when_set(self):
        with mock.patch.dict(os.environ, {"OLLAMA_HOST": "box:9999"}):
            self.assertEqual(ask.default_host(), "http://box:9999")
        env = {k: v for k, v in os.environ.items() if k != "OLLAMA_HOST"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(ask.default_host(), "http://localhost:11434")


class Speed(unittest.TestCase):
    def test_missing_duration_is_none(self):
        self.assertIsNone(ask.tokens_per_second(100, None))
        self.assertIsNone(ask.tokens_per_second(100, 0))

    def test_valid(self):
        self.assertEqual(ask.tokens_per_second(100, 2_000_000_000), 50.0)


class ExitCodes(unittest.TestCase):
    def run_main(self, argv, prompt="short prompt", result=None, side_effect=None, model_ctx=None):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "prompt.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(prompt)
            full = [a if a != "{FILE}" else p for a in argv]
            out, err = io.StringIO(), io.StringIO()
            patcher = mock.patch.object(ask, "call_ollama", side_effect=side_effect, return_value=result)
            ctx_patch = mock.patch.object(ask, "MODEL_CTX", model_ctx if model_ctx is not None else {"m": 2048})
            with patcher as m, ctx_patch, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = ask.main(full)
            return code, out.getvalue(), err.getvalue(), m

    GOOD = {"response": "hi", "prompt_eval_count": 50, "eval_count": 5,
            "prompt_eval_duration": 1_000_000_000, "eval_duration": 1_000_000_000,
            "done_reason": "stop"}

    def test_ok(self):
        code, out, _, _ = self.run_main(["--model", "m", "--file", "{FILE}"], result=dict(self.GOOD))
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["truncated"], False)
        self.assertEqual(data["done_reason"], "stop")
        self.assertEqual(data["cut_by_predict"], False)

    def test_cut_by_predict(self):
        res = dict(self.GOOD, done_reason="length")
        code, out, _, _ = self.run_main(["--model", "m", "--file", "{FILE}"], result=res)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["cut_by_predict"])

    def test_missing_durations_give_null_speeds(self):
        res = {"response": "hi", "prompt_eval_count": 50, "eval_count": 5}
        code, out, _, _ = self.run_main(["--model", "m", "--file", "{FILE}"], result=res)
        data = json.loads(out)
        self.assertIsNone(data["prompt_tok_s"])
        self.assertIsNone(data["gen_tok_s"])

    def test_truncation_is_4(self):
        res = dict(self.GOOD, prompt_eval_count=2048)
        code, out, err, _ = self.run_main(["--model", "m", "--file", "{FILE}"], result=res)
        self.assertEqual(code, 4)
        self.assertTrue(json.loads(out)["truncated"])
        self.assertIn("truncat", err.lower())

    def test_unverified_is_4(self):
        res = dict(self.GOOD, prompt_eval_count=0)
        code, out, _, _ = self.run_main(["--model", "m", "--file", "{FILE}"], result=res)
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["truncation_status"], "unverified")

    def test_connect_error_is_3(self):
        code, _, err, _ = self.run_main(["--model", "m", "--file", "{FILE}"],
                                        side_effect=RuntimeError("Cannot reach Ollama"))
        self.assertEqual(code, 3)
        self.assertNotIn("Traceback", err)

    def test_timeout_and_bad_json_are_3(self):
        for exc in (TimeoutError("t"), json.JSONDecodeError("bad", "x", 0), OSError("boom")):
            code, _, err, _ = self.run_main(["--model", "m", "--file", "{FILE}"], side_effect=exc)
            self.assertEqual(code, 3, repr(exc))
            self.assertNotIn("Traceback", err)

    def test_missing_ceiling_is_2(self):
        code, _, _, m = self.run_main(["--model", "other", "--file", "{FILE}"], result=dict(self.GOOD))
        self.assertEqual(code, 2)
        m.assert_not_called()

    def test_nonpositive_num_ctx_is_2(self):
        for bad in ("0", "-5"):
            code, _, err, m = self.run_main(["--model", "m", "--num-ctx", bad, "--file", "{FILE}"],
                                            result=dict(self.GOOD))
            self.assertEqual(code, 2)
            m.assert_not_called()

    def test_preflight_refusal_is_4_and_skips_call(self):
        big = "x" * 5000  # ~1428 tokens vs 0.9 * 1000 ctx
        code, _, err, m = self.run_main(["--model", "m", "--num-ctx", "1000", "--file", "{FILE}"],
                                        prompt=big, result=dict(self.GOOD))
        self.assertEqual(code, 4)
        m.assert_not_called()
        self.assertIn("--force", err)

    def test_force_bypasses_preflight(self):
        big = "x" * 5000
        code, _, _, m = self.run_main(["--model", "m", "--num-ctx", "1000", "--force", "--file", "{FILE}"],
                                      prompt=big, result=dict(self.GOOD))
        self.assertEqual(code, 0)
        m.assert_called_once()

    def test_unreadable_file_is_2(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ask, "MODEL_CTX", {"m": 2048}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ask.main(["--model", "m", "--file", "/no/such/file.txt"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
