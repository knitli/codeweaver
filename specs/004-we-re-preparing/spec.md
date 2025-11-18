<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Feature Specification: PyPI Build and Publishing System

**Feature Branch**: `004-we-re-preparing`
**Created**: 2025-10-27
**Status**: Complete - Ready for Planning
**Input**: User description: "we're preparing for CodeWeaver's v.10 release (its first), and in order to do that, it needs to have a working build process to publish to pypi. So this is a pretty straight forward spec -- we need a build system."

## Execution Flow (main)
```
1. Parse user description from Input
   � If empty: ERROR "No feature description provided"
2. Extract key concepts from description
   � Identify: actors, actions, data, constraints
3. For each unclear aspect:
   � Mark with [NEEDS CLARIFICATION: specific question]
4. Fill User Scenarios & Testing section
   � If no clear user flow: ERROR "Cannot determine user scenarios"
5. Generate Functional Requirements
   � Each requirement must be testable
   � Mark ambiguous requirements
6. Identify Key Entities (if data involved)
7. Run Review Checklist
   � If any [NEEDS CLARIFICATION]: WARN "Spec has uncertainties"
   � If implementation details found: ERROR "Remove tech details"
8. Return: SUCCESS (spec ready for planning)
```

---

## � Quick Guidelines
-  Focus on WHAT users need and WHY
- L Avoid HOW to implement (no tech stack, APIs, code structure)
- =e Written for business stakeholders, not developers

### Section Requirements
- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation
When creating this spec from a user prompt:
1. **Mark all ambiguities**: Use [NEEDS CLARIFICATION: specific question] for any assumption you'd need to make
2. **Don't guess**: If the prompt doesn't specify something (e.g., "login system" without auth method), mark it
3. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
4. **Common underspecified areas**:
   - User types and permissions
   - Data retention/deletion policies
   - Performance targets and scale
   - Error handling behaviors
   - Integration requirements
   - Security/compliance needs

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a **package maintainer**, I need to reliably build and publish CodeWeaver releases to PyPI so that users can install the package using standard Python package managers.

As a **CI/CD system**, I need to automate the build and publishing process so that releases are consistent, reproducible, and free from manual errors.

As an **end user**, I need access to stable, versioned releases on PyPI so that I can install and manage CodeWeaver as a dependency in my projects.

### Acceptance Scenarios
1. **Given** a tagged release commit, **When** the build process is triggered, **Then** a distributable package is created containing all necessary source files and metadata
2. **Given** a successfully built package, **When** uploaded to PyPI, **Then** the package is installable via `pip install codeweaver`
3. **Given** multiple Python versions (3.12, 3.13, 3.14), **When** a user installs the package, **Then** the package works correctly on all supported versions
4. **Given** an untagged commit, **When** building the package, **Then** the version is automatically derived as a per-commit pre-release version (e.g., "0.0.1rc295+gfc4f90a")
5. **Given** pending changesets, **When** preparing a release, **Then** the version is coordinated with the changeset workflow
6. **Given** a failed build, **When** reviewing build output, **Then** clear error messages indicate what went wrong and how to fix it
7. **Given** project metadata (authors, license, description), **When** building the package, **Then** all metadata is correctly included in the distribution
8. **Given** dependencies specified in project configuration, **When** building the package, **Then** dependency information is correctly embedded for installation
9. **Given** GitHub Actions OAuth is configured, **When** publishing to PyPI, **Then** authentication occurs automatically without manual token management
10. **Given** a built package, **When** CI tests run on Python 3.12, 3.13, and 3.14, **Then** all tests pass before publication is allowed

### Edge Cases
- What happens when building from a commit without a version tag? (System should generate per-commit version like "0.0.1rc295+gfc4f90a")
- How does the system handle version bumps coordinated with changesets?
- What happens if required build tools are missing or outdated?
- How are build artifacts cleaned up after successful/failed builds?
- What happens when publishing to PyPI with an already-existing version number?
- How does the system verify package integrity before publishing?
- What happens when GitHub Actions OAuth authentication fails or is not configured?

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: System MUST create distributable packages in standard Python formats (wheel and source distribution)
- **FR-002**: System MUST automatically derive version numbers from git repository state
- **FR-003**: System MUST include all necessary source code, metadata, and license information in distributions
- **FR-004**: System MUST validate package integrity before allowing publication
- **FR-005**: System MUST support publishing to PyPI and TestPyPI repositories
- **FR-006**: System MUST preserve reproducibility by documenting exact build environment and dependencies
- **FR-007**: System MUST provide clear success/failure feedback for all build and publish operations
- **FR-008**: System MUST prevent accidental re-publication of existing version numbers
- **FR-009**: System MUST support per-commit pre-release versioning (e.g., "0.0.1rc295+gfc4f90a") using existing version management tooling
- **FR-010**: System MUST integrate with existing changeset workflow for version management
- **FR-011**: System MUST clean up build artifacts after completion to prevent workspace pollution
- **FR-012**: System MUST be automatable for CI/CD environments without manual intervention
- **FR-013**: System MUST ensure Python version compatibility (3.12, 3.13, 3.14) is verified by CI pipeline before allowing publication to PyPI
- **FR-014**: Build process MUST complete within reasonable time without being excessively long
- **FR-015**: System MUST use GitHub Actions OAuth-based authentication for PyPI publishing (trusted publishing)
- **FR-016**: System MUST support dry-run mode for testing build process without publishing

### Key Entities *(include if feature involves data)*
- **Package Distribution**: The compiled/packaged form of CodeWeaver ready for installation, containing source code, metadata, and dependencies
- **Version Identifier**: A unique version number derived from repository state, following semantic versioning conventions
- **Build Manifest**: Record of exact build environment, dependencies, and configuration used to create a distribution
- **PyPI Repository**: External package index where distributions are published (production or test)
- **Metadata Bundle**: Collection of project information (name, authors, license, description, classifiers) embedded in distributions

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---

## Notes for Planning Phase

This specification intentionally avoids prescribing implementation details (specific build backends, tooling choices, or workflow orchestration). The focus is on **what** capabilities the build system must provide and **why** they matter for the v0.1.0 release.

### Clarifications Received
1. ✅ **Versioning**: Using uv-versioning for automatic per-commit versions (e.g., "0.0.1rc295+gfc4f90a")
2. ✅ **Changesets**: Integration with existing changeset workflow for version management
3. ✅ **PyPI Authentication**: GitHub Actions OAuth (trusted publishing) already configured
4. ✅ **Build Time**: Should complete in "reasonable time, not super long" (further optimization targets to be determined during planning)
5. ✅ **Python Version Testing**: CI pipeline already tests Python 3.12-3.14; build process delegates validation to CI rather than duplicating testing at build time

### Planning Phase Considerations
- Build system must integrate with existing uv-versioning configuration
- Build system must work with existing changeset workflow
- Build system must leverage existing GitHub Actions OAuth setup
- Build performance optimization targets can be established during planning based on current baseline measurements
