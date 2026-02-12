#!/usr/bin/env python
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Verification script for migration state machine test suite.

This script verifies the completeness and correctness of the state machine
test suite before it's used as the specification for implementation.
"""

import sys

from pathlib import Path


def verify_test_suite() -> int:
    """Verify the migration state machine test suite is complete.

    Returns:
        0 if verification passes, 1 if any checks fail
    """
    print("=" * 70)
    print("Migration State Machine Test Suite Verification")
    print("=" * 70)
    print()

    # Import the test module
    try:
        import test_migration_state_machine as tsm

        print("✅ Test module imports successfully")
    except ImportError as e:
        print(f"❌ Failed to import test module: {e}")
        return 1

    # Verify state definition
    states = list(tsm.MigrationState)
    print(f"✅ MigrationState enum defined with {len(states)} states")
    print(f"   States: {[s.value for s in states]}")

    expected_states = {"pending", "in_progress", "completed", "failed", "rollback"}
    actual_states = {s.value for s in states}
    if actual_states != expected_states:
        print(f"❌ State mismatch! Expected {expected_states}, got {actual_states}")
        return 1

    # Verify valid transitions
    total_transitions = sum(len(v) for v in tsm.VALID_TRANSITIONS.values())
    print(f"✅ VALID_TRANSITIONS defined with {total_transitions} transitions")

    # Verify all states have outgoing transitions or are reachable
    for state in states:
        has_outgoing = state in tsm.VALID_TRANSITIONS
        is_target = any(state in targets for targets in tsm.VALID_TRANSITIONS.values())
        if not (has_outgoing or is_target):
            print(f"❌ State {state} is isolated (neither source nor target)")
            return 1

    print("✅ All states are reachable or have outgoing transitions")

    # Count test classes and methods
    test_classes = [x for x in dir(tsm) if x.startswith("Test")]
    total_tests = 0
    test_class_counts = {}

    for cls_name in test_classes:
        cls = getattr(tsm, cls_name)
        methods = [m for m in dir(cls) if m.startswith("test_") and callable(getattr(cls, m))]
        test_class_counts[cls_name] = len(methods)
        total_tests += len(methods)

    print(f"✅ Found {len(test_classes)} test classes with {total_tests} test methods")
    print()
    print("Test Class Breakdown:")
    for cls_name, count in sorted(test_class_counts.items()):
        print(f"   {cls_name}: {count} tests")

    # Verify required test classes exist
    required_classes = {
        "TestValidStateTransitions",
        "TestInvalidStateTransitions",
        "TestStateTransitionAtomicity",
        "TestStateReachability",
        "TestStatePersistence",
        "TestConcurrentStateTransitions",
        "TestStateMachineProperties",
    }

    missing_classes = required_classes - set(test_classes)
    if missing_classes:
        print(f"❌ Missing required test classes: {missing_classes}")
        return 1

    print("✅ All required test classes present")

    # Verify helper functions exist
    required_helpers = {
        "create_migration",
        "can_transition",
        "transition",
        "transition_async",
        "get_valid_transitions",
        "find_path",
        "save_migration",
        "load_migration",
    }

    available_helpers = {name for name in dir(tsm) if not name.startswith("_")}
    missing_helpers = required_helpers - available_helpers
    if missing_helpers:
        print(f"❌ Missing required helper functions: {missing_helpers}")
        return 1

    print(f"✅ All {len(required_helpers)} required helper functions present")

    # Verify exception class exists
    if not hasattr(tsm, "InvalidStateTransitionError"):
        print("❌ InvalidStateTransitionError exception class not defined")
        return 1

    print("✅ InvalidStateTransitionError exception class defined")

    # Verify Migration dataclass exists
    if not hasattr(tsm, "Migration"):
        print("❌ Migration dataclass not defined")
        return 1

    print("✅ Migration dataclass defined")

    # Check for hypothesis availability
    try:
        import hypothesis

        print(f"✅ hypothesis library available (version {hypothesis.__version__})")
    except ImportError:
        print("⚠️  hypothesis library not installed (property tests will skip)")

    # Summary
    print()
    print("=" * 70)
    print("Verification Summary")
    print("=" * 70)
    print(f"States: {len(states)}")
    print(f"Valid Transitions: {total_transitions}")
    print(f"Test Classes: {len(test_classes)}")
    print(f"Test Methods: {total_tests}")
    print(f"Helper Functions: {len(required_helpers)}")
    print()
    print("✅ ALL VERIFICATIONS PASSED")
    print()
    print("The test suite is ready to serve as the specification")
    print("for migration service implementation.")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    # Add parent directory to path to import test module
    sys.path.insert(0, str(Path(__file__).parent))

    exit_code = verify_test_suite()
    sys.exit(exit_code)
