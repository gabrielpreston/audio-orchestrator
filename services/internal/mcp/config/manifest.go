package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Manifest represents the top-level structure of an MCP manifest file.
type Manifest struct {
	Servers map[string]ServerConfig `json:"mcpServers"`
}

// ServerConfig describes how to connect to a single MCP server.
type ServerConfig struct {
	Transport *TransportConfig  `json:"transport,omitempty"`
	Command   string            `json:"command,omitempty"`
	Args      []string          `json:"args,omitempty"`
	Env       map[string]string `json:"env,omitempty"`
	Enabled   *bool             `json:"enabled,omitempty"`
}

// TransportConfig captures remote connection information for an MCP server.
type TransportConfig struct {
	Type string `json:"type"`
	URL  string `json:"url,omitempty"`
}

// Result holds the merged configuration after loading all manifest sources.
type Result struct {
	Servers map[string]ServerConfig
	Order   []string
	Sources []string
}

// LoadResult loads the MCP configuration, merging workspace and user manifests.
func LoadResult() (Result, error) {
	result := Result{Servers: make(map[string]ServerConfig)}

	overridePath := os.Getenv("MCP_CONFIG_PATH")
	if overridePath != "" {
		path, err := expandPath(overridePath)
		if err != nil {
			return result, err
		}
		manifest, err := readManifest(path)
		if err != nil {
			return result, err
		}
		mergeServers(result.Servers, manifest.Servers)
		result.Sources = append(result.Sources, path)
		finalizeOrder(&result)
		return result, nil
	}

	workspacePath, err := workspaceManifestPath()
	switch {
	case err == nil:
		if manifest, err := readManifest(workspacePath); err == nil {
			mergeServers(result.Servers, manifest.Servers)
			result.Sources = append(result.Sources, workspacePath)
		} else if !errors.Is(err, os.ErrNotExist) {
			return result, err
		}
	case err != nil && !errors.Is(err, os.ErrNotExist):
		return result, err
	}

	userPath, err := userManifestPath()
	switch {
	case err == nil:
		if manifest, err := readManifest(userPath); err == nil {
			mergeServers(result.Servers, manifest.Servers)
			result.Sources = append(result.Sources, userPath)
		} else if !errors.Is(err, os.ErrNotExist) {
			return result, err
		}
	case err != nil && !errors.Is(err, os.ErrNotExist):
		return result, err
	}

	finalizeOrder(&result)
	return result, nil
}

// Enabled reports whether the server should be used.
func (s ServerConfig) EnabledValue() bool {
	if s.Enabled == nil {
		return true
	}
	return *s.Enabled
}

func finalizeOrder(result *Result) {
	names := make([]string, 0, len(result.Servers))
	for name := range result.Servers {
		names = append(names, name)
	}
	sort.Strings(names)
	result.Order = names
}

func mergeServers(dst map[string]ServerConfig, src map[string]ServerConfig) {
	if len(src) == 0 {
		return
	}
	for name, cfg := range src {
		normalized := normalizeConfig(cfg)
		dst[name] = normalized
	}
}

func normalizeConfig(cfg ServerConfig) ServerConfig {
	if cfg.Args != nil {
		out := make([]string, len(cfg.Args))
		for i, arg := range cfg.Args {
			if expanded, err := expandPath(arg); err == nil {
				out[i] = expanded
			} else {
				out[i] = arg
			}
		}
		cfg.Args = out
	}
	if cfg.Command != "" {
		if expanded, err := expandPath(cfg.Command); err == nil {
			cfg.Command = expanded
		}
	}
	if len(cfg.Env) > 0 {
		env := make(map[string]string, len(cfg.Env))
		for k, v := range cfg.Env {
			if expanded, err := expandPath(v); err == nil {
				env[k] = expanded
			} else {
				env[k] = v
			}
		}
		cfg.Env = env
	}
	if cfg.Transport != nil && cfg.Transport.URL != "" {
		if expanded, err := expandPath(cfg.Transport.URL); err == nil {
			cfg.Transport.URL = expanded
		}
	}
	return cfg
}

func readManifest(path string) (Manifest, error) {
	f, err := os.Open(path)
	if err != nil {
		return Manifest{}, err
	}
	defer f.Close()

	data, err := io.ReadAll(f)
	if err != nil {
		return Manifest{}, err
	}
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return Manifest{}, fmt.Errorf("parse %s: %w", path, err)
	}
	if manifest.Servers == nil {
		manifest.Servers = make(map[string]ServerConfig)
	}
	return manifest, nil
}

func workspaceManifestPath() (string, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	path := filepath.Join(cwd, ".discord-voice-lab", "mcp.json")
	if _, err := os.Stat(path); err != nil {
		return path, err
	}
	return path, nil
}

func userManifestPath() (string, error) {
	base := os.Getenv("XDG_CONFIG_HOME")
	if base == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		base = filepath.Join(home, ".config")
	}
	path := filepath.Join(base, "discord-voice-lab", "mcp.json")
	if _, err := os.Stat(path); err != nil {
		return path, err
	}
	return path, nil
}

func expandPath(value string) (string, error) {
	if value == "" {
		return value, nil
	}
	if strings.HasPrefix(value, "~") {
		home, err := os.UserHomeDir()
		if err != nil {
			return value, err
		}
		if value == "~" {
			return home, nil
		}
		if strings.HasPrefix(value, "~/") {
			return filepath.Join(home, value[2:]), nil
		}
		return filepath.Join(home, value[1:]), nil
	}
	return value, nil
}
