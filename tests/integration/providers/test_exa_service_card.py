# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration test for Exa service card resolution.

This test verifies that the Exa data provider service card can successfully
resolve its lateimport references, preventing the latent bug described in
issue #311 where the service card referenced a non-existent ExaToolset class.
"""

import pytest


@pytest.mark.integration
@pytest.mark.unit  # Also mark as unit since it doesn't require external services
class TestExaServiceCardResolution:
    """Test that the Exa service card can resolve its provider class."""

    def test_exa_service_card_lateimport_resolution(self):
        """Test that the Exa service card's lateimport can resolve to exa_toolset.

        This test verifies the fix for issue #311 where the service card
        referenced a non-existent 'ExaToolset' class instead of the actual
        'exa_toolset' async factory function.
        """
        from codeweaver.core.types.service_cards import get_service_cards

        # Get the Exa service card
        cards = get_service_cards(provider="exa", category="data")
        assert len(cards) == 1, "Expected exactly one Exa data provider service card"

        card = cards[0]

        # Verify the card exists and has the expected structure
        assert card.provider == "exa"
        assert card.category == "data"

        # Attempt to resolve the provider class - this will raise AttributeError
        # if the lateimport references a non-existent attribute
        provider_cls = card.provider_cls._resolve()

        # Verify we got a callable (the exa_toolset function)
        assert callable(provider_cls), "Provider class should be callable"

        # Verify it's the correct function by checking its name
        assert provider_cls.__name__ == "exa_toolset", (
            f"Expected provider class to be 'exa_toolset', got '{provider_cls.__name__}'"
        )

    def test_exa_service_card_client_resolution(self):
        """Test that the Exa service card's client lateimport resolves correctly."""
        from codeweaver.core.types.service_cards import get_service_cards

        cards = get_service_cards(provider="exa", category="data")
        card = cards[0]

        # Verify the client class can be resolved
        # This will raise an ImportError if exa_py is not installed,
        # which is expected behavior (the service card should handle this gracefully)
        try:
            client_cls = card.client_cls._resolve()
            assert client_cls is not None
            assert client_cls.__name__ == "AsyncExa"
        except ImportError:
            # If exa_py is not installed, that's fine - the test is just checking
            # that the lateimport reference is correct
            pytest.skip("exa_py package not installed")

    def test_exa_service_card_has_metadata(self):
        """Test that the Exa service card has the expected metadata."""
        from codeweaver.core.types.service_cards import get_service_cards

        cards = get_service_cards(provider="exa", category="data")
        card = cards[0]

        # Verify the card has metadata
        assert card.metadata is not None, "Exa service card should have metadata"

        # Verify it has a provider_handler
        assert hasattr(card.metadata, "provider_handler"), (
            "Exa service card metadata should have a provider_handler"
        )
        assert callable(card.metadata.provider_handler), (
            "provider_handler should be callable"
        )

    def test_exa_service_card_provider_handler_extracts_tool_config(self):
        """Test that the provider_handler extracts tool_config from DI-shaped config.

        The DI system passes ExaProviderSettings as `config`, but exa_toolset()
        expects ExaToolConfig | None. The handler must extract .tool_config from
        the settings object before forwarding to exa_toolset, avoiding a runtime
        type error when providers are instantiated through DI.
        """
        from types import SimpleNamespace

        from codeweaver.core.types.service_cards import get_service_cards
        from codeweaver.providers.config.sdk.data import ExaToolConfig

        cards = get_service_cards(provider="exa", category="data")
        assert len(cards) == 1, "Expected exactly one Exa data provider service card"
        card = cards[0]

        # Build a settings-shaped object that mirrors ExaProviderSettings.
        # The DI factory sets provider_kwargs["config"] = settings (the full settings
        # object), so the handler must extract settings.tool_config for exa_toolset.
        tool_config = ExaToolConfig()
        di_config = SimpleNamespace(tool_config=tool_config)

        # Capture what config the handler passes to the provider factory.
        captured: dict[str, object] = {}

        def mock_exa_toolset(client: object, *, config: object = None, **kwargs: object) -> list:
            captured["config"] = config
            return []

        handler = card.metadata.provider_handler
        handler(mock_exa_toolset, card, client=None, config=di_config)

        # The handler must extract .tool_config, not pass the whole settings object.
        assert captured.get("config") is tool_config, (
            "provider_handler must extract ExaProviderSettings.tool_config and pass it "
            "to exa_toolset, not the whole settings object"
        )
