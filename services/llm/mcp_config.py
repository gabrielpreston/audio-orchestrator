"""MCP configuration loader for parsing mcp.json and managing server definitions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.common.logging import get_logger

logger = get_logger(__name__, service_name="llm")


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    enabled: bool = True


class MCPConfig:
    """Loads and manages MCP server configurations from mcp.json."""
    
    def __init__(self, config_path: str = "./mcp.json"):
        self.config_path = Path(config_path)
        self.servers: Dict[str, MCPServerConfig] = {}
        self._logger = get_logger(__name__, service_name="llm")
    
    def load(self) -> None:
        """Load MCP server configurations from mcp.json."""
        if not self.config_path.exists():
            self._logger.warning(
                "mcp.config_file_missing",
                path=str(self.config_path),
            )
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            mcp_servers = data.get("mcpServers", {})
            
            for name, config in mcp_servers.items():
                if not isinstance(config, dict):
                    self._logger.warning(
                        "mcp.invalid_server_config",
                        name=name,
                        reason="not_dict",
                    )
                    continue
                
                command = config.get("command")
                if not command:
                    self._logger.warning(
                        "mcp.invalid_server_config",
                        name=name,
                        reason="missing_command",
                    )
                    continue
                
                args = config.get("args", [])
                if not isinstance(args, list):
                    self._logger.warning(
                        "mcp.invalid_server_config",
                        name=name,
                        reason="args_not_list",
                    )
                    continue
                
                env = config.get("env", {})
                if not isinstance(env, dict):
                    self._logger.warning(
                        "mcp.invalid_server_config",
                        name=name,
                        reason="env_not_dict",
                    )
                    continue
                
                # Substitute environment variables in args
                processed_args = [self._substitute_env_vars(arg) for arg in args]
                processed_env = {k: self._substitute_env_vars(v) for k, v in env.items()}
                
                server_config = MCPServerConfig(
                    name=name,
                    command=command,
                    args=processed_args,
                    env=processed_env,
                    enabled=config.get("enabled", True),
                )
                
                self.servers[name] = server_config
                
                self._logger.info(
                    "mcp.server_config_loaded",
                    name=name,
                    command=command,
                    args=processed_args,
                    enabled=server_config.enabled,
                )
            
            self._logger.info(
                "mcp.config_loaded",
                server_count=len(self.servers),
                path=str(self.config_path),
            )
            
        except json.JSONDecodeError as exc:
            self._logger.error(
                "mcp.config_parse_failed",
                path=str(self.config_path),
                error=str(exc),
            )
            raise
        except Exception as exc:
            self._logger.error(
                "mcp.config_load_failed",
                path=str(self.config_path),
                error=str(exc),
            )
            raise
    
    def get_enabled_servers(self) -> Dict[str, MCPServerConfig]:
        """Get all enabled MCP server configurations."""
        return {name: config for name, config in self.servers.items() if config.enabled}
    
    def get_server_config(self, name: str) -> Optional[MCPServerConfig]:
        """Get configuration for a specific server."""
        return self.servers.get(name)
    
    def _substitute_env_vars(self, value: str) -> str:
        """Substitute environment variables in a string value."""
        if not isinstance(value, str):
            return value
        
        # Simple environment variable substitution
        # Supports ${VAR} and $VAR syntax
        import re
        
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return os.getenv(var_name, match.group(0))
        
        # Match ${VAR} or $VAR
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        return re.sub(pattern, replace_var, value)


__all__ = ["MCPConfig", "MCPServerConfig"]
