#!/usr/bin/env python3
"""Behavior-parity test runner for the Python noise-chatbot.

Mirror of ``REFERENCE/parity/runner.py`` (Phase A4 deliverable) but drives
a Python harness against Python ``noise-helper`` rather than Go binaries.

Usage:

    python3 runner.py *.yaml
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("ERROR: PyYAML required. pip install pyyaml\n")
    sys.exit(2)


@dataclass
class Harness:
    proc: subprocess.Popen[str]
    host_port: str
    pubkey: str

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def start_harness(
    harness_cmd: list[str], config: dict[str, Any], startup_timeout: float = 5.0
) -> Harness:
    proc = subprocess.Popen(
        harness_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(config))
    proc.stdin.close()

    end = time.time() + startup_timeout
    while time.time() < end:
        line = proc.stdout.readline()
        if not line:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"harness exited before READY — stderr:\n{stderr}")
        line = line.strip()
        if line.startswith("READY "):
            _, host_port, pubkey = line.split(" ", 2)
            return Harness(proc=proc, host_port=host_port, pubkey=pubkey)
    proc.terminate()
    raise RuntimeError(f"harness did not emit READY within {startup_timeout}s")


@dataclass
class HelperSession:
    proc: subprocess.Popen[str]
    _buf: str = ""

    def send(self, msg: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout: float = 5.0) -> dict[str, Any]:
        import select

        assert self.proc.stdout is not None
        end = time.time() + timeout
        while "\n" not in self._buf and time.time() < end:
            remaining = max(0.01, end - time.time())
            rlist, _, _ = select.select([self.proc.stdout], [], [], remaining)
            if not rlist:
                continue
            chunk = os.read(self.proc.stdout.fileno(), 65536).decode("utf-8", errors="replace")
            if not chunk:
                raise RuntimeError("helper stdout closed before response")
            self._buf += chunk
        if "\n" not in self._buf:
            raise TimeoutError(f"no response within {timeout}s")
        line, self._buf = self._buf.split("\n", 1)
        decoded: dict[str, Any] = json.loads(line)
        return decoded

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                assert self.proc.stdin is not None
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def connect_helper(
    helper_cmd: list[str], host_port: str, pubkey: str, timeout: float = 5.0
) -> HelperSession:
    proc = subprocess.Popen(
        [*helper_cmd, "--server", host_port, "--key", pubkey],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )
    assert proc.stdout is not None
    end = time.time() + timeout
    while time.time() < end:
        line = proc.stdout.readline()
        if not line:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"helper exited before CONNECTED — stderr:\n{stderr}")
        line = line.strip()
        if line == "CONNECTED":
            return HelperSession(proc=proc)
    proc.terminate()
    raise TimeoutError("helper did not print CONNECTED")


@dataclass
class FixtureResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    observed: list[dict[str, Any]] = field(default_factory=list)


def run_fixture(
    fixture: dict[str, Any], harness_cmd: list[str], helper_cmd: list[str]
) -> FixtureResult:
    name = fixture.get("name", "<unnamed>")
    result = FixtureResult(name=name, passed=True)

    if fixture.get("skip"):
        result.errors.append(f"SKIPPED: {fixture.get('skip_reason', 'manually skipped')}")
        return result

    harness_cfg = fixture.get("harness", {}) or {}
    interactions = fixture.get("interactions", []) or []

    try:
        harness = start_harness(harness_cmd, harness_cfg)
    except Exception as exc:
        result.errors.append(f"harness start failed: {exc}")
        result.passed = False
        return result

    try:
        session = connect_helper(helper_cmd, harness.host_port, harness.pubkey)
    except Exception as exc:
        result.errors.append(f"helper connect failed: {exc}")
        result.passed = False
        harness.stop()
        return result

    try:
        for i, ixn in enumerate(interactions):
            if "delay_seconds" in ixn:
                time.sleep(float(ixn["delay_seconds"]))
                continue

            if not ixn.get("expect_only"):
                send = ixn.get("send")
                if send is not None:
                    session.send(send)

            expect = ixn.get("expect")
            if expect is None:
                continue

            try:
                timeout = float(expect.get("timeout_seconds", 5.0))
                resp = session.recv(timeout=timeout)
            except TimeoutError as exc:
                if expect.get("expect_no_response"):
                    continue
                result.errors.append(f"interaction {i}: {exc}")
                result.passed = False
                break

            result.observed.append(resp)
            for err in compare(resp, expect):
                result.errors.append(f"interaction {i}: {err}")
                result.passed = False
    finally:
        session.close()
        harness.stop()

    return result


def compare(observed: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errs = []
    if "type" in expect and observed.get("type") != expect["type"]:
        errs.append(f"type mismatch: expected {expect['type']!r}, got {observed.get('type')!r}")
    if "reply_to" in expect and observed.get("reply_to") != expect["reply_to"]:
        errs.append(
            f"reply_to mismatch: expected {expect['reply_to']!r}, got {observed.get('reply_to')!r}"
        )

    payload = observed.get("payload", {})
    if isinstance(payload, str):
        with contextlib.suppress(Exception):
            payload = json.loads(payload)

    if "payload_text" in expect:
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        sub = expect["payload_text"]
        if sub not in text:
            errs.append(f"payload.text substring mismatch: expected {sub!r} \u2282 {text!r}")

    if "payload_text_exact" in expect:
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        want = expect["payload_text_exact"]
        if text != want:
            errs.append(f"payload.text exact mismatch: expected {want!r}, got {text!r}")

    if "error_payload" in expect:
        err_text = payload.get("error", "") if isinstance(payload, dict) else ""
        want = expect["error_payload"]
        if err_text != want:
            errs.append(f"payload.error mismatch: expected {want!r}, got {err_text!r}")

    if "payload_equals" in expect and payload != expect["payload_equals"]:
        errs.append(f"payload mismatch: expected {expect['payload_equals']!r}, got {payload!r}")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fixtures", nargs="+", type=Path)
    ap.add_argument(
        "--harness",
        nargs="+",
        default=[sys.executable, "-m", "tests.parity.harness"],
        help="harness command (default: python3 -m tests.parity.harness)",
    )
    ap.add_argument(
        "--helper",
        nargs="+",
        default=[sys.executable, "-m", "noise_chatbot.helper.main"],
        help="helper command (default: python3 -m noise_chatbot.helper.main)",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    total = 0
    passed = 0
    failed: list[FixtureResult] = []

    for path in args.fixtures:
        with open(path) as f:
            fixture = yaml.safe_load(f)
        total += 1
        result = run_fixture(fixture, args.harness, args.helper)
        skipped = any(e.startswith("SKIPPED") for e in result.errors)
        status = "SKIP" if skipped else ("PASS" if result.passed else "FAIL")
        print(f"[{status}] {path.name}: {result.name}")
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed.append(result)
            for err in result.errors:
                print(f"    \u2022 {err}")
            if args.verbose and result.observed:
                print(f"    observed: {json.dumps(result.observed, indent=2)}")

    skipped_count = total - passed - len(failed)
    print(f"\n{passed}/{total} passed ({len(failed)} failed, {skipped_count} skipped)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
