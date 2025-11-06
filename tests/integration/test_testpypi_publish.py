# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test: TestPyPI publish workflow validation."""

import pytest


@pytest.mark.integration
@pytest.mark.external_api
@pytest.mark.skip(reason="Requires GitHub Actions infrastructure - manual validation required")
def test_publish_to_testpypi():
    """
    Integration test for TestPyPI publish workflow.

    This test validates the complete TestPyPI publishing workflow:
    1. Trigger publish-test.yml workflow (manual dispatch)
    2. Wait for workflow completion
    3. Verify package appears on test.pypi.org
    4. Attempt installation from TestPyPI
    5. Verify package functionality

    NOTE: This test requires:
    - GitHub Actions workflow dispatch capability
    - TestPyPI trusted publisher configuration
    - Network access to test.pypi.org

    Manual validation steps:
    1. Go to GitHub Actions
    2. Select "Publish to TestPyPI" workflow
    3. Click "Run workflow"
    4. Wait for completion
    5. Visit https://test.pypi.org/project/codeweaver-mcp/
    6. Verify package appears with correct version
    7. Test installation: pip install --index-url https://test.pypi.org/simple/ codeweaver-mcp
    """
    pytest.skip("Requires manual GitHub Actions workflow execution")
