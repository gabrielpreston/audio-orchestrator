"""
Example of how to use the common debug library in the Discord service.

This shows how any service can save debug files using the centralized debug manager.
"""

from services.common.debug import (get_debug_manager, save_debug_json,
                                   save_debug_text)


def example_discord_debug_usage():
    """Example of how the Discord service could use debug functionality."""

    # Method 1: Using the debug manager directly
    debug_manager = get_debug_manager("discord")

    correlation_id = "discord-12345-67890"

    # Save debug text
    debug_manager.save_text_file(
        correlation_id=correlation_id,
        content="Discord voice segment processed\nUser: 12345\nChannel: 67890",
        filename_prefix="voice_segment",
    )

    # Save debug JSON data
    debug_manager.save_json_file(
        correlation_id=correlation_id,
        data={
            "user_id": "12345",
            "channel_id": "67890",
            "guild_id": "98765",
            "audio_duration": 2.5,
            "sample_rate": 48000,
        },
        filename_prefix="voice_metadata",
    )

    # Save manifest
    debug_manager.save_manifest(
        correlation_id=correlation_id,
        metadata={
            "service": "discord",
            "event": "voice_segment_processed",
            "user_id": "12345",
        },
        files={
            "voice_segment": "voice_segment.txt",
            "metadata": "voice_metadata.json",
        },
        stats={
            "audio_duration": 2.5,
            "sample_rate": 48000,
        },
    )


def example_convenience_functions():
    """Example using convenience functions."""

    correlation_id = "discord-54321-98765"

    # Using convenience functions
    save_debug_text(
        correlation_id=correlation_id,
        content="Discord MCP tool called: play_audio",
        service_name="discord",
        filename_prefix="mcp_call",
    )

    save_debug_json(
        correlation_id=correlation_id,
        data={
            "tool": "play_audio",
            "guild_id": "98765",
            "channel_id": "54321",
            "audio_url": "http://orchestrator:8000/audio/test.wav",
        },
        service_name="discord",
        filename_prefix="mcp_request",
    )


if __name__ == "__main__":
    example_discord_debug_usage()
    example_convenience_functions()
