#!/usr/bin/env python3
"""Behavior-parity test runner for the Go noise-chatbot.

Drives the Go harness binary with fixture-defined configurations, sends
messages via noise-helper, and asserts responses match expectations.

Usage:

    runner.py --harness /tmp/parity-harness --helper /tmp/noise-helper \\
        fixtures/*.yaml

Or use --capture to write observed outputs back into each fixture's
`expected_golden:` block (Go-golden capture mode, per the lab book).

Fixture format — one YAML file per test:

    name: <id>
    package: server | noise | protocol | client | helper
    function: <name>
    description: <human text>
    trl: |
      AGENT harness SHALL ...
    harness:                          # passed to harness stdin as JSON
      chat_handler: echo
      responses: []
      greeting: ""
      contact_footer: ""
      ...
    interactions:
      - send:                         # JSON message written to helper stdin
          type: CHAT
          payload: {text: "hello"}
          id: msg-1
        expect:                       # optional; one response is consumed
          type: CHAT
          payload_text: "You said: hello"   # substring match
          payload_text_exact: null          # exact match (mutually exclusive)
          reply_to: msg-1
          error_payload: null               # exact match on payload.error
      - expect_only: true             # consume next message without sending
        expect: { ... }
      - delay_seconds: 2              # sleep before next interaction
    notes: |
      Free-form.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. pip install pyyaml\n")
    sys.exit(2)


# ─────────────────────────────────────────────────────────────────────────
# Harness lifecycle
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class Harness:
    proc: subprocess.Popen
    host_port: str
    pubkey: str

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def start_harness(harness_bin: Path, config: dict, startup_timeout: float = 5.0) -> Harness:
    """Start the Go harness with the given config, return host:port + pubkey."""
    proc = subprocess.Popen(
        [str(harness_bin)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(config))
    proc.stdin.close()

    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            # harness died
            stderr_output = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"harness exited before READY — stderr:\n{stderr_output}")
        line = line.strip()
        if line.startswith("READY "):
            _, host_port, pubkey = line.split(" ", 2)
            return Harness(proc=proc, host_port=host_port, pubkey=pubkey)
    proc.terminate()
    raise RuntimeError(f"harness did not emit READY within {startup_timeout}s")


# ─────────────────────────────────────────────────────────────────────────
# Helper client
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class HelperSession:
    proc: subprocess.Popen

    def send(self, msg: dict) -> None:
        assert self.proc.stdin is not None
        line = json.dumps(msg) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def recv(self, timeout: float = 5.0) -> dict:
        """Read one JSON line from helper stdout within timeout seconds."""
        assert self.proc.stdout is not None
        # Use a select-based approach for portability
        import select
        end = time.time() + timeout
        buf = ""
        while time.time() < end:
            remaining = max(0.01, end - time.time())
            rlist, _, _ = select.select([self.proc.stdout], [], [], remaining)
            if not rlist:
                continue
            chunk = os.read(self.proc.stdout.fileno(), 65536).decode("utf-8", errors="replace")
            if not chunk:
                raise RuntimeError("helper stdout closed before response")
            buf += chunk
            if "\n" in buf:
                line, rest = buf.split("\n", 1)
                if rest:
                    # Put rest back — we only serve one message at a time
                    self._pushback = rest
                return json.loads(line)
        raise TimeoutError(f"no response within {timeout}s")

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                assert self.proc.stdin is not None
                self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def connect_helper(helper_bin: Path, host_port: str, pubkey: str, timeout: float = 5.0) -> HelperSession:
    proc = subprocess.Popen(
        [str(helper_bin), "--server", host_port, "--key", pubkey],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )
    assert proc.stdout is not None
    # Wait for "CONNECTED" line
    end = time.time() + timeout
    while time.time() < end:
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"helper exited before CONNECTED — stderr:\n{err}")
        line = line.strip()
        if line == "CONNECTED":
            return HelperSession(proc=proc)
    proc.terminate()
    raise TimeoutError("helper did not print CONNECTED")


# ─────────────────────────────────────────────────────────────────────────
# Fixture execution
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class FixtureResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    observed: list[dict] = field(default_factory=list)


def run_fixture(fixture: dict, harness_bin: Path, helper_bin: Path) -> FixtureResult:
    name = fixture.get("name", "<unnamed>")
    result = FixtureResult(name=name, passed=True)

    harness_cfg = fixture.get("harness", {}) or {}
    interactions = fixture.get("interactions", []) or []

    if fixture.get("skip"):
        result.errors.append(f"SKIPPED: {fixture.get('skip_reason', 'manually skipped')}")
        result.passed = False  # treated as neutral — caller checks errors prefix
        return result

    try:
        harness = start_harness(harness_bin, harness_cfg)
    except Exception as exc:
        result.errors.append(f"harness start failed: {exc}")
        result.passed = False
        return result

    try:
        session = connect_helper(helper_bin, harness.host_port, harness.pubkey)
    except Exception as exc:
        result.errors.append(f"helper connect failed: {exc}")
        result.passed = False
        harness.stop()
        return result

    # Some fixtures expect the server to push a greeting before any send.
    # Those fixtures put a greeting expectation as interactions[0] with
    # expect_only: true.
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
                    # No response expected — timeout is the pass
                    continue
                result.errors.append(f"interaction {i}: {exc}")
                result.passed = False
                break

            result.observed.append(resp)

            errors = compare(resp, expect)
            for err in errors:
                result.errors.append(f"interaction {i}: {err}")
                result.passed = False
    finally:
        session.close()
        harness.stop()

    return result


def compare(observed: dict, expect: dict) -> list[str]:
    errs = []

    if "type" in expect and observed.get("type") != expect["type"]:
        errs.append(f"type mismatch: expected {expect['type']!r}, got {observed.get('type')!r}")

    if "reply_to" in expect and observed.get("reply_to") != expect["reply_to"]:
        errs.append(f"reply_to mismatch: expected {expect['reply_to']!r}, got {observed.get('reply_to')!r}")

    payload = observed.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            pass
    # payload may arrive as a JSON-encoded string, or as a nested object when
    # the client unmarshals it. Normalise.
    if isinstance(observed.get("payload"), str):
        try:
            payload = json.loads(observed["payload"])
        except Exception:
            pass

    if "payload_text" in expect:
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        sub = expect["payload_text"]
        if sub not in text:
            errs.append(f"payload.text substring mismatch: expected {sub!r} ⊂ {text!r}")

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

    if "payload_equals" in expect:
        if payload != expect["payload_equals"]:
            errs.append(f"payload mismatch: expected {expect['payload_equals']!r}, got {payload!r}")

    return errs


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fixtures", nargs="+", type=Path, help="YAML fixture files")
    ap.add_argument("--harness", type=Path, default=Path("/tmp/parity-harness"),
                    help="Path to the Go parity-harness binary")
    ap.add_argument("--helper", type=Path, default=Path("/tmp/noise-helper"),
                    help="Path to the Go noise-helper binary")
    ap.add_argument("-v", "--verbose", action="store_true", help="Show observed messages on failure")
    args = ap.parse_args()

    if not args.harness.exists():
        sys.stderr.write(f"ERROR: harness binary not found at {args.harness}\n")
        return 2
    if not args.helper.exists():
        sys.stderr.write(f"ERROR: helper binary not found at {args.helper}\n")
        return 2

    total = 0
    passed = 0
    failed_fixtures: list[FixtureResult] = []

    for path in args.fixtures:
        with open(path) as f:
            fixture = yaml.safe_load(f)
        total += 1
        result = run_fixture(fixture, args.harness, args.helper)
        status = "PASS" if result.passed and not any(e.startswith("SKIPPED") for e in result.errors) else \
                 "SKIP" if any(e.startswith("SKIPPED") for e in result.errors) else "FAIL"
        print(f"[{status}] {path.name}: {result.name}")
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed_fixtures.append(result)
            for err in result.errors:
                print(f"    • {err}")
            if args.verbose and result.observed:
                print(f"    observed: {json.dumps(result.observed, indent=2)}")

    skipped = total - passed - len(failed_fixtures)
    print(f"\n{passed}/{total} passed ({len(failed_fixtures)} failed, {skipped} skipped)")
    return 0 if not failed_fixtures else 1


if __name__ == "__main__":
    sys.exit(main())
