package voice

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/discord-voice-lab/internal/logging"
)

// SidecarManager centralizes finding and updating JSON sidecar files stored
// in a configured directory. If Dir is empty the manager is a no-op.
type SidecarManager struct {
	Dir string
}

func NewSidecarManager(dir string) *SidecarManager {
	if strings.TrimSpace(dir) == "" {
		return nil
	}
	return &SidecarManager{Dir: dir}
}

// FindByCID returns the full path to the sidecar JSON matching correlation id
// or an empty string if not found.
func (s *SidecarManager) FindByCID(cid string) string {
	if s == nil || s.Dir == "" || cid == "" {
		return ""
	}
	files, _ := os.ReadDir(s.Dir)
	for _, fi := range files {
		name := fi.Name()
		if !strings.HasSuffix(name, ".json") {
			continue
		}
		path := s.Dir + "/" + name
		if b, err := os.ReadFile(path); err == nil {
			var sc map[string]interface{}
			if err := json.Unmarshal(b, &sc); err == nil {
				if v, ok := sc["correlation_id"].(string); ok && v == cid {
					return path
				}
			}
		}
	}
	// fallback: filename contains cid
	for _, fi := range files {
		name := fi.Name()
		if strings.Contains(name, "cid"+cid) && strings.HasSuffix(name, ".json") {
			return s.Dir + "/" + name
		}
	}
	return ""
}

// MergeUpdatesForCID reads the sidecar JSON for cid, merges the provided
// updates into it, and writes the file back atomically. Returns an error
// if the sidecar cannot be found or updated.
func (s *SidecarManager) MergeUpdatesForCID(cid string, updates map[string]interface{}) error {
	if s == nil {
		return fmt.Errorf("sidecar manager not configured")
	}
	path := s.FindByCID(cid)
	if path == "" {
		return fmt.Errorf("sidecar not found for cid=%s", cid)
	}
	sb, rerr := os.ReadFile(path)
	if rerr != nil {
		logging.Debugw("sidecar: failed to read sidecar for cid", "path", path, "err", rerr, "correlation_id", cid)
		return rerr
	}
	var sc map[string]interface{}
	if uerr := json.Unmarshal(sb, &sc); uerr != nil {
		logging.Debugw("sidecar: failed to unmarshal sidecar JSON", "path", path, "err", uerr, "correlation_id", cid)
		return uerr
	}
	for k, v := range updates {
		sc[k] = v
	}
	nb, _ := json.MarshalIndent(sc, "", "  ")
	_ = os.WriteFile(path+".tmp", nb, 0o644)
	if err := os.Rename(path+".tmp", path); err != nil {
		logging.Debugw("sidecar: failed to rename tmp file", "tmp", path+".tmp", "final", path, "err", err, "correlation_id", cid)
		return err
	}
	logging.Infow("sidecar: saved updates", "path", path, "correlation_id", cid)
	return nil
}
