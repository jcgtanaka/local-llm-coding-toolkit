"""Unit tests for benchmark/benchmark_model.py (pure logic, no network)."""
import contextlib
import importlib.util
import io
import json
import os
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def load_module(name, rel_path):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bm = load_module("benchmark_model", "benchmark/benchmark_model.py")


class TruncationRule(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(bm.assess_truncation(500, 2048), "ok")
        self.assertEqual(bm.assess_truncation(2027, 2048), "ok")
        self.assertEqual(bm.assess_truncation(2028, 2048), "truncated")
        self.assertEqual(bm.assess_truncation(0, 2048), "unverified")
        self.assertEqual(bm.assess_truncation(None, 2048), "unverified")
        self.assertEqual(bm.truncation_margin(100), 8)


class HostNormalization(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(bm.normalize_host("myhost:11434"), "http://myhost:11434")
        self.assertEqual(bm.normalize_host("https://x.example/"), "https://x.example")
        self.assertEqual(bm.normalize_host(None), "http://localhost:11434")


class Speed(unittest.TestCase):
    def test_cases(self):
        self.assertIsNone(bm.tokens_per_second(10, None))
        self.assertIsNone(bm.tokens_per_second(10, 0))
        self.assertEqual(bm.tokens_per_second(100, 2_000_000_000), 50.0)


class BuildPrompt(unittest.TestCase):
    def test_contains_both_facts_and_is_near_target(self):
        target = 20000
        p = bm.build_prompt(target)
        self.assertIn("ALPHA-7429", p)
        self.assertIn("BRAVO-1836", p)
        self.assertLess(abs(len(p) - target), target * 0.02)
        self.assertLess(p.index("ALPHA-7429"), p.index("BRAVO-1836"))

    def test_middle_fact_is_roughly_in_the_middle(self):
        p = bm.build_prompt(20000)
        frac = p.index("BRAVO-1836") / len(p)
        self.assertTrue(0.4 < frac < 0.6)


class GpuShare(unittest.TestCase):
    def test_full_gpu(self):
        data = {"models": [{"name": "m:latest", "size": 1000, "size_vram": 1000}]}
        self.assertEqual(bm.gpu_split_from_ps(data, "m:latest"), "100% GPU")

    def test_partial(self):
        data = {"models": [{"name": "m:latest", "size": 1000, "size_vram": 450}]}
        self.assertEqual(bm.gpu_split_from_ps(data, "m:latest"), "45% GPU / 55% CPU")

    def test_exact_name_only(self):
        data = {"models": [{"name": "m:7b", "size": 1000, "size_vram": 1000}]}
        self.assertTrue(bm.gpu_split_from_ps(data, "m:70b").startswith("not detected"))

    def test_bare_name_matches_latest_tag(self):
        data = {"models": [{"name": "m:latest", "size": 1000, "size_vram": 0}]}
        self.assertEqual(bm.gpu_split_from_ps(data, "m"), "0% GPU / 100% CPU")

    def test_zero_size_or_empty(self):
        self.assertTrue(bm.gpu_split_from_ps({"models": []}, "m").startswith("not detected"))
        data = {"models": [{"name": "m", "size": 0, "size_vram": 0}]}
        self.assertTrue(bm.gpu_split_from_ps(data, "m").startswith("not detected"))


class RunOne(unittest.TestCase):
    GOOD = {"response": "ALPHA-7429 BRAVO-1836", "prompt_eval_count": 100, "eval_count": 5,
            "prompt_eval_duration": 1_000_000_000, "eval_duration": 1_000_000_000}

    def test_fill_above_one_flags_saturation(self):
        res = dict(self.GOOD, prompt_eval_count=2048)
        with mock.patch.object(bm, "call_ollama", return_value=res), \
                mock.patch.object(bm, "get_gpu_split", return_value="100% GPU"):
            row = bm.run_one("http://h", "m", 2048, 16, fill=1.2, timeout=5)
        self.assertTrue(row["truncated"])
        self.assertEqual(row["truncation_status"], "truncated")

    def test_default_fill_ok(self):
        with mock.patch.object(bm, "call_ollama", return_value=dict(self.GOOD)), \
                mock.patch.object(bm, "get_gpu_split", return_value="100% GPU"):
            row = bm.run_one("http://h", "m", 8192, 16, fill=0.85, timeout=5)
        self.assertFalse(row["truncated"])
        self.assertTrue(row["recalled_both"])

    def test_errors_are_recorded_not_raised(self):
        for exc in (RuntimeError("x"), TimeoutError("t"), json.JSONDecodeError("b", "x", 0), OSError("o")):
            with mock.patch.object(bm, "call_ollama", side_effect=exc):
                row = bm.run_one("http://h", "m", 2048, 16, fill=0.85, timeout=5)
            self.assertTrue(row["error"], repr(exc))


class MainExit(unittest.TestCase):
    def run_main(self, side_effect):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(bm, "call_ollama", side_effect=side_effect), \
                mock.patch.object(bm, "get_gpu_split", return_value="100% GPU"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = bm.main(["--model", "m", "--ctx", "2048,4096"])
        return code, out.getvalue()

    def test_all_fail_is_nonzero_and_full_error_printed(self):
        long_msg = "E" * 80
        code, out = self.run_main(RuntimeError(long_msg))
        self.assertEqual(code, 3)
        self.assertIn(long_msg, out)

    def test_partial_failure_is_zero(self):
        good = RunOne.GOOD
        code, _ = self.run_main([RuntimeError("x"), dict(good)])
        self.assertEqual(code, 0)

    def test_all_ok_is_zero(self):
        good = RunOne.GOOD
        code, _ = self.run_main([dict(good), dict(good)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
