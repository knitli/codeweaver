# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ruff: noqa: S603
"""
Comprehensive test script for fix-ruff-patterns.sh
Generates test files with various ruff violations and validates fixes.
"""

import shutil
import subprocess
import sys

from pathlib import Path
from typing import cast


class RuffPatternTester:
    """Test the fix-ruff-patterns.sh script with generated problematic files."""

    def __init__(self, test_dir: str = "test_batch") -> None:
        """Initialize the tester with a test directory."""
        self.test_dir = Path(test_dir)
        self.script_dir = Path(__file__).parent
        self.fix_script = self.script_dir / "fix-ruff-patterns.sh"

    def setup_test_environment(self) -> None:
        """Create test directory and clean up any existing files."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True)
        print(f"✅ Created test directory: {self.test_dir}")

    def generate_test_files(self) -> dict[str, str]:
        """Generate test files with various ruff violations."""
        test_files = {
            "g004_fstrings.py": '\nimport logging\n\nlogger = logging.getLogger(__name__)\n\ndef test_g004_violations():\n    user_id = 123\n    error_msg = "connection failed"\n    value = 42\n\n    # Simple f-string cases\n    logger.info("Processing user %s", user_id)\n    logger.error("Error occurred: %s", error_msg)\n    logger.debug("Value is %s", value)\n\n    # Complex f-string cases\n    logger.warning("User %s has %s items", user_id, len([1,2,3]))\n    logger.critical("Failed to process %s with error: %s", user_id, error_msg)\n\n    # Nested expressions\n    data = {"key": "value"}\n    logger.info("Data: %s", data.get(\'key\', \'default\'))\n\n    # Multiple variables\n    x, y = 10, 20\n    logger.debug("Coordinates: (%s, %s)", x, y)\n',
            "try401_exceptions.py": '\nimport logging\n\nlogger = logging.getLogger(__name__)\n\ndef test_try401_violations():\n    try:\n        risky_operation()\n    except Exception as e:\n        # Basic redundant exception cases\n        logger.exception("Failed: ")\n        logger.exception("Error occurred - ")\n        logger.exception("Connection timeout ()")\n        logger.exception("Database error, ")\n        logger.exception("Processing failed .")\n\n        # F-string redundant exceptions\n        logger.exception("Failed with error: ")\n        logger.exception("Database connection failed - ")\n        logger.exception("Timeout occurred ()")\n\n    try:\n        another_operation()\n    except ValueError as exc:\n        logger.exception("Value error: ")\n        logger.exception("Invalid value: ")\n\n    try:\n        third_operation()\n    except (TypeError, AttributeError) as exception:\n        logger.exception("Type/Attribute error: ")\n        logger.exception("Error details: ")\n\ndef risky_operation():\n    pass\n\ndef another_operation():\n    pass\n\ndef third_operation():\n    pass\n',
            "try300_returns.py": '\ndef test_try300_violations():\n    # Simple try/return case\n    try:\n        result = calculate_simple()\n        return result\n    except ValueError:\n        return None\n\n    # Try/return with as clause\n    try:\n        data = fetch_data()\n        return data\n    except ConnectionError as e:\n        log_error(e)\n        return {}\n\n    # Multiple statements before return\n    try:\n        x = process_input()\n        y = validate(x)\n        z = transform(y)\n        return z\n    except (ValueError, TypeError):\n        return None\n\n    # Multiple except blocks\n    try:\n        result = complex_operation()\n        return result\n    except ValueError as ve:\n        handle_value_error(ve)\n        return "value_error"\n    except TypeError as te:\n        handle_type_error(te)\n        return "type_error"\n\n    # Bare except\n    try:\n        dangerous_operation()\n        return "success"\n    except:\n        return "failed"\n\ndef calculate_simple():\n    return 42\n\ndef fetch_data():\n    return {"data": "value"}\n\ndef process_input():\n    return "processed"\n\ndef validate(x):\n    return x\n\ndef transform(y):\n    return y.upper()\n\ndef complex_operation():\n    return "complex_result"\n\ndef log_error(e):\n    pass\n\ndef handle_value_error(e):\n    pass\n\ndef handle_type_error(e):\n    pass\n\ndef dangerous_operation():\n    pass\n',
            "mixed_violations.py": '\nimport logging\n\nlogger = logging.getLogger(__name__)\n\ndef mixed_violations_test():\n    user_id = 456\n\n    # G004 + TRY401 combination\n    try:\n        process_user(user_id)\n        return "success"  # TRY300\n    except Exception as e:\n        logger.exception("Failed to process user %s: %s", user_id, e)  # G004 + TRY401\n        return None\n\n    # More complex mixed case\n    try:\n        data = fetch_user_data(user_id)\n        logger.info("Fetched data for user %s", user_id)  # G004\n        result = process_data(data)\n        return result  # TRY300\n    except ValueError as ve:\n        logger.exception("Value error occurred: %s", ve)  # TRY401\n        return {}\n    except Exception as e:\n        logger.error("Unexpected error: %s", e)  # G004 + TRY401 (error, not exception)\n        return None\n\ndef process_user(user_id):\n    pass\n\ndef fetch_user_data(user_id):\n    return {"id": user_id}\n\ndef process_data(data):\n    return data\n',
            "edge_cases.py": '\nimport logging\n\nlogger = logging.getLogger(__name__)\nlog = logging.getLogger("test")\n\ndef edge_cases():\n    # Different logger names\n    try:\n        operation()\n    except Exception as e:\n        log.exception("Failed: ")  # Different logger variable\n\n    # Nested try blocks\n    try:\n        try:\n            inner_operation()\n            return "inner_success"  # TRY300 in nested try\n        except ValueError:\n            return "inner_failed"\n    except Exception as e:\n        logger.exception("Outer exception: ")  # G004 + TRY401\n\n    # Complex f-strings\n    user = {"name": "John", "id": 123}\n    try:\n        process_user_complex(user)\n    except Exception as e:\n        logger.exception("Failed for user %s (ID: %s): %s", user[\'name\'], user[\'id\'], e)\n\n    # Multiple returns in try\n    try:\n        if condition_a():\n            return "a"\n        elif condition_b():\n            return "b"\n        else:\n            return "c"\n    except Exception:\n        return "error"\n\ndef operation():\n    pass\n\ndef inner_operation():\n    pass\n\ndef process_user_complex(user):\n    pass\n\ndef condition_a():\n    return False\n\ndef condition_b():\n    return True\n',
        }
        for filename, content in test_files.items():
            file_path = self.test_dir / filename
            file_path.write_text(content)
            print(f"✅ Generated {filename}")
        return test_files

    def run_ruff_check(self, target: str | None = None) -> tuple[bool, str]:
        """Run ruff check on target and return (success, output)."""
        target = target or str(self.test_dir)
        try:
            result = subprocess.run(
                [
                    cast(bytes, shutil.which("ruff")),
                    "check",
                    target,
                    "--select=TRY401,G004,TRY300",
                    "--no-fix",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return (False, f"Ruff check failed: {e}")
        else:
            return (result.returncode == 0, result.stdout + result.stderr)

    def run_fix_script(self, targets: list[str] | None = None) -> tuple[bool, str]:
        """Run the fix-ruff-patterns.sh script."""
        if targets is None:
            targets = [str(self.script_dir / self.test_dir)]
        else:
            targets = [
                target if Path(target).is_absolute() else str(self.script_dir / target)
                for target in targets
            ]
        try:
            result = subprocess.run(
                [str(self.fix_script), *targets, "--debug"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                cwd=self.script_dir.parent,
            )
            success = result.returncode == 0
            output = result.stdout
            if not success:
                output += f"\n[DEBUG] Fix script returned exit code: {result.returncode}"
        except subprocess.TimeoutExpired:
            return (False, "Fix script timed out")
        except Exception as e:
            return (False, f"Fix script failed: {e}")
        else:
            return (success, output)

    def analyze_changes(self, test_files: dict[str, str]) -> dict[str, dict]:
        """Analyze what changes were made to each file."""
        changes = {}
        for filename, original_content in test_files.items():
            file_path = self.test_dir / filename
            if file_path.exists():
                current_content = file_path.read_text()
                changes[filename] = {
                    "modified": current_content != original_content,
                    "original_lines": len(original_content.splitlines()),
                    "current_lines": len(current_content.splitlines()),
                    "content": current_content,
                }
            else:
                changes[filename] = {"error": "File not found after processing"}
        return changes

    def validate_fixes(self, changes: dict[str, dict]) -> dict[str, list[str]]:
        """Validate that the fixes are correct."""
        validation_results = {}
        for filename, change_info in changes.items():
            issues = []
            if "error" in change_info:
                issues.append(change_info["error"])
                continue
            content = change_info["content"]
            if 'f"' in content or "f'" in content:
                lines = content.splitlines()
                issues.extend(
                    (
                        f"Line {i}: Possible remaining G004 violation: {line.strip()}"
                        for i, line in enumerate(lines, 1)
                        if ("logger." in line or "logging." in line or "log." in line)
                        and ('f"' in line or "f'" in line)
                    )
                )
            lines = content.splitlines()
            issues.extend(
                (
                    f"Line {i}: Possible remaining TRY401 violation: {line.strip()}"
                    for i, line in enumerate(lines, 1)
                    if ".exception(" in line
                    and (")" in line or ", exc)" in line or ", exception)" in line)
                )
            )
            in_try = False
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("try:"):
                    in_try = True
                elif stripped.startswith("except"):
                    in_try = False
                elif in_try and stripped.startswith("return "):
                    issues.append(f"Line {i}: Possible remaining TRY300 violation: {line.strip()}")
            validation_results[filename] = issues
        return validation_results

    def run_comprehensive_test(self) -> bool:
        # sourcery skip: no-long-functions
        """Run the complete test suite."""
        print("🚀 Starting comprehensive test of fix-ruff-patterns.sh")
        print("=" * 60)
        self.setup_test_environment()
        print("\n📝 Generating test files...")
        test_files = self.generate_test_files()
        print("\n🔍 Checking initial ruff violations...")
        initial_success, initial_output = self.run_ruff_check()
        if initial_success:
            print(
                "⚠️  No initial violations found - this might indicate a problem with test generation"
            )
        else:
            violation_count = (
                initial_output.count("TRY401")
                + initial_output.count("G004")
                + initial_output.count("TRY300")
            )
            print(f"✅ Found {violation_count} violations as expected")
            print("Sample violations:")
            for line in initial_output.splitlines()[:10]:
                if any(code in line for code in ["TRY401", "G004", "TRY300"]):
                    print(f"  {line}")
        print("\n🔧 Running fix-ruff-patterns.sh...")
        fix_success, fix_output = self.run_fix_script()
        print("Fix script output:")
        print("-" * 40)
        print(fix_output)
        print("-" * 40)
        if not fix_success:
            print("❌ Fix script failed!")
            return False
        print("\n📊 Analyzing changes...")
        changes = self.analyze_changes(test_files)
        modified_files = [f for f, info in changes.items() if info.get("modified", False)]
        print(f"✅ Modified {len(modified_files)} files: {', '.join(modified_files)}")
        print("\n✅ Validating fixes...")
        validation_results = self.validate_fixes(changes)
        total_issues = sum(len(issues) for issues in validation_results.values())
        if total_issues == 0:
            print("🎉 All fixes appear correct!")
        else:
            print(f"⚠️  Found {total_issues} potential issues:")
            for filename, issues in validation_results.items():
                if issues:
                    print(f"  {filename}:")
                    for issue in issues:
                        print(f"    - {issue}")
        print("\n🎯 Final ruff verification...")
        final_success, final_output = self.run_ruff_check()
        if final_success:
            print("🎉 Perfect! No remaining violations!")
        else:
            remaining_violations = (
                final_output.count("TRY401")
                + final_output.count("G004")
                + final_output.count("TRY300")
            )
            print(f"⚠️  {remaining_violations} violations remain:")
            for line in final_output.splitlines():
                if any(code in line for code in ["TRY401", "G004", "TRY300"]):
                    print(f"  {line}")
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        print(f"Test files generated: {len(test_files)}")
        print(f"Files modified: {len(modified_files)}")
        print(f"Validation issues: {total_issues}")
        print(f"Final ruff check: {('PASSED' if final_success else 'FAILED')}")
        success = final_success and total_issues == 0
        print(f"Overall result: {('✅ SUCCESS' if success else '❌ FAILED')}")
        return success

    def cleanup(self) -> None:
        """Clean up test directory."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            print(f"🧹 Cleaned up {self.test_dir}")


def main() -> None:
    """Main test runner."""
    tester = RuffPatternTester()
    try:
        success = tester.run_comprehensive_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if "--keep-files" not in sys.argv:
            tester.cleanup()
        else:
            print(f"📁 Test files preserved in {tester.test_dir}")


if __name__ == "__main__":
    main()
