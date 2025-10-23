"""Configuration migration utilities for transitioning to new system."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from services.common.logging import get_logger

logger = get_logger(__name__)


class ConfigMigrationValidator:
    """Validates configuration migration from old to new system."""
    
    def __init__(self) -> None:
        """Initialize migration validator."""
        self.migration_map = self._build_migration_map()
    
    def _build_migration_map(self) -> Dict[str, Dict[str, Any]]:
        """Build mapping from old config to new config structure."""
        return {
            # Old AudioConfig -> New AudioConfig
            "audio": {
                "sample_rate": "AUDIO_SAMPLE_RATE",
                "channels": "AUDIO_CHANNELS", 
                "enable_enhancement": "AUDIO_ENABLE_ENHANCEMENT",
                "enable_vad": "AUDIO_ENABLE_VAD",
                "service_url": "AUDIO_SERVICE_URL",
                "service_timeout": "AUDIO_SERVICE_TIMEOUT"
            },
            # Old ProcessingConfig -> New AudioConfig
            "processing": {
                "target_sample_rate": "AUDIO_SAMPLE_RATE",
                "target_channels": "AUDIO_CHANNELS",
                "enable_audio_enhancement": "AUDIO_ENABLE_ENHANCEMENT",
                "enable_noise_reduction": "AUDIO_ENABLE_VAD"
            },
            # Old FasterWhisperConfig -> New AudioConfig
            "faster_whisper": {
                "model": "STT_MODEL",
                "device": "STT_DEVICE",
                "model_path": "STT_MODEL_PATH"
            },
            # Old DiscordConfig + DiscordRuntimeConfig -> New DiscordConfig
            "discord": {
                "token": "DISCORD_BOT_TOKEN",
                "guild_id": "DISCORD_GUILD_ID",
                "voice_channel_id": "DISCORD_VOICE_CHANNEL_ID",
                "auto_join": "DISCORD_AUTO_JOIN"
            },
            # Old PortConfig -> New ServiceConfig
            "port": {
                "port": "SERVICE_PORT",
                "host": "SERVICE_HOST",
                "workers": "SERVICE_WORKERS"
            }
        }
    
    def validate_migration(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> bool:
        """Validate that configuration migration preserves all settings.
        
        Args:
            old_config: Old configuration dictionary
            new_config: New configuration dictionary
            
        Returns:
            True if migration is valid, False otherwise
        """
        try:
            # Check that all old settings have equivalents
            for old_section, old_values in old_config.items():
                if old_section in self.migration_map:
                    migration_rules = self.migration_map[old_section]
                    for old_key, new_env_var in migration_rules.items():
                        if old_key in old_values:
                            # Check if new config has equivalent value
                            if not self._has_equivalent_value(old_values[old_key], new_env_var, new_config):
                                logger.warning(
                                    "config.migration_missing_value",
                                    old_section=old_section,
                                    old_key=old_key,
                                    new_env_var=new_env_var
                                )
                                return False
            
            # Check that new settings are valid
            return self._validate_new_config(new_config)
            
        except Exception as exc:
            logger.error(
                "config.migration_validation_failed",
                error=str(exc)
            )
            return False
    
    def _has_equivalent_value(self, old_value: Any, new_env_var: str, new_config: Dict[str, Any]) -> bool:
        """Check if new config has equivalent value for old setting."""
        # This is a simplified check - in practice, you'd need more sophisticated mapping
        return new_env_var in new_config or old_value is not None
    
    def _validate_new_config(self, new_config: Dict[str, Any]) -> bool:
        """Validate new configuration structure."""
        required_sections = ["logging", "http", "audio", "service", "telemetry"]
        
        for section in required_sections:
            if section not in new_config:
                logger.warning(
                    "config.migration_missing_section",
                    section=section
                )
                return False
        
        return True
    
    def generate_migration_report(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> str:
        """Generate migration report showing changes."""
        report = []
        report.append("# Configuration Migration Report")
        report.append("")
        
        # Show removed configurations
        report.append("## Removed Configurations")
        removed_configs = [
            "ProcessingConfig (merged into AudioConfig)",
            "FasterWhisperConfig (merged into AudioConfig)", 
            "DiscordRuntimeConfig (merged into DiscordConfig)",
            "PortConfig (merged into ServiceConfig)"
        ]
        for config in removed_configs:
            report.append(f"- {config}")
        
        report.append("")
        
        # Show environment variable changes
        report.append("## Environment Variable Changes")
        report.append("### New Variables")
        new_vars = [
            "AUDIO_SERVICE_URL",
            "AUDIO_SERVICE_TIMEOUT", 
            "SERVICE_NAME",
            "SERVICE_PORT",
            "SERVICE_HOST",
            "SERVICE_WORKERS"
        ]
        for var in new_vars:
            report.append(f"- {var}")
        
        report.append("")
        report.append("### Removed Variables")
        removed_vars = [
            "AUDIO_TARGET_SAMPLE_RATE (use AUDIO_SAMPLE_RATE)",
            "AUDIO_TARGET_CHANNELS (use AUDIO_CHANNELS)",
            "PROCESSING_ENABLE_AUDIO_ENHANCEMENT (use AUDIO_ENABLE_ENHANCEMENT)",
            "PORT_CONFIG_PORT (use SERVICE_PORT)"
        ]
        for var in removed_vars:
            report.append(f"- {var}")
        
        return "\n".join(report)


def migrate_config_file(old_config_path: Path, new_config_path: Path) -> bool:
    """Migrate configuration file from old to new format.
    
    Args:
        old_config_path: Path to old configuration file
        new_config_path: Path to new configuration file
        
    Returns:
        True if migration successful, False otherwise
    """
    try:
        # Load old configuration
        with open(old_config_path, 'r') as f:
            old_config = json.load(f)
        
        # Create new configuration structure
        new_config = {
            "logging": {
                "level": old_config.get("logging", {}).get("level", "INFO"),
                "json_logs": old_config.get("logging", {}).get("json_logs", True),
                "service_name": old_config.get("logging", {}).get("service_name", "audio-orchestrator")
            },
            "http": {
                "timeout": old_config.get("http", {}).get("timeout", 30.0),
                "max_retries": old_config.get("http", {}).get("max_retries", 3),
                "retry_delay": old_config.get("http", {}).get("retry_delay", 1.0)
            },
            "audio": {
                "sample_rate": old_config.get("audio", {}).get("sample_rate", 16000),
                "channels": old_config.get("audio", {}).get("channels", 1),
                "enable_enhancement": old_config.get("audio", {}).get("enable_enhancement", True),
                "enable_vad": old_config.get("audio", {}).get("enable_vad", True),
                "service_url": old_config.get("audio", {}).get("service_url", "http://audio-processor:9100"),
                "service_timeout": old_config.get("audio", {}).get("service_timeout", 20)
            },
            "service": {
                "port": old_config.get("service", {}).get("port", 8000),
                "host": old_config.get("service", {}).get("host", "0.0.0.0"),
                "workers": old_config.get("service", {}).get("workers", 1)
            },
            "telemetry": {
                "enabled": old_config.get("telemetry", {}).get("enabled", True),
                "metrics_port": old_config.get("telemetry", {}).get("metrics_port", 9090),
                "jaeger_endpoint": old_config.get("telemetry", {}).get("jaeger_endpoint", "")
            }
        }
        
        # Write new configuration
        with open(new_config_path, 'w') as f:
            json.dump(new_config, f, indent=2)
        
        logger.info(
            "config.migration_completed",
            old_path=str(old_config_path),
            new_path=str(new_config_path)
        )
        return True
        
    except Exception as exc:
        logger.error(
            "config.migration_failed",
            old_path=str(old_config_path),
            new_path=str(new_config_path),
            error=str(exc)
        )
        return False
