package voice

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"syscall"

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
	files, derr := os.ReadDir(s.Dir)
	if derr != nil {
		logging.Warnw("sidecar: failed to list dir", "dir", s.Dir, "err", derr)
		return ""
	}
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
		} else {
			// surface read errors at debug so operators can inspect problematic files
			logging.Debugw("sidecar: failed to read file while searching by cid", "path", path, "err", err, "correlation_id", cid)
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
		return fmt.Errorf("sidecar not found for cid=%s (searched dir=%s)", cid, s.Dir)
	}
	// If locking is enabled, acquire an advisory lock on path + ".lock"
	doLock := strings.ToLower(strings.TrimSpace(os.Getenv("SIDECAR_LOCKING"))) == "true"
	var lockFile *os.File
	if doLock {
		lf := path + ".lock"
		f, ferr := os.OpenFile(lf, os.O_CREATE|os.O_RDWR, 0o644)
		if ferr != nil {
			logging.Warnw("sidecar: failed to open lock file", "lock", lf, "err", ferr, "correlation_id", cid)
			return fmt.Errorf("failed to open lock file %s: %w", lf, ferr)
		}
		lockFile = f
		if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
			_ = f.Close()
			logging.Warnw("sidecar: failed to flock lock file", "lock", lf, "err", err, "correlation_id", cid)
			return fmt.Errorf("failed to lock file %s: %w", lf, err)
		}
		// We hold the lock until we explicitly unlock/close below
	}

	sb, rerr := os.ReadFile(path)
	if rerr != nil {
		// Ensure lock is released if we failed while holding it
		if lockFile != nil {
			_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
			_ = lockFile.Close()
		}
		logging.Warnw("sidecar: failed to read sidecar for cid", "path", path, "err", rerr, "correlation_id", cid)
		return fmt.Errorf("failed to read sidecar %s: %w", path, rerr)
	}
	var sc map[string]interface{}
	if uerr := json.Unmarshal(sb, &sc); uerr != nil {
		logging.Warnw("sidecar: failed to unmarshal sidecar JSON", "path", path, "err", uerr, "correlation_id", cid)
		return fmt.Errorf("invalid sidecar JSON %s: %w", path, uerr)
	}
	for k, v := range updates {
		sc[k] = v
	}
	nb, merr := json.MarshalIndent(sc, "", "  ")
	if merr != nil {
		if lockFile != nil {
			_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
			_ = lockFile.Close()
		}
		logging.Warnw("sidecar: failed to marshal updated JSON", "path", path, "err", merr, "correlation_id", cid)
		return fmt.Errorf("failed to marshal updated sidecar JSON for %s: %w", path, merr)
	}
	tmpPath := path + ".tmp"
	f, ferr := os.OpenFile(tmpPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if ferr != nil {
		if lockFile != nil {
			_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
			_ = lockFile.Close()
		}
		logging.Warnw("sidecar: failed to create tmp file", "tmp", tmpPath, "err", ferr, "correlation_id", cid)
		return fmt.Errorf("failed to create temp file %s: %w", tmpPath, ferr)
	}
	// write and fsync to ensure data hits disk before rename
	if _, werr := f.Write(nb); werr != nil {
		_ = f.Close()
		logging.Warnw("sidecar: failed to write tmp file", "tmp", tmpPath, "err", werr, "correlation_id", cid)
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to write temp file %s: %w", tmpPath, werr)
	}
	if serr := f.Sync(); serr != nil {
		_ = f.Close()
		if lockFile != nil {
			_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
			_ = lockFile.Close()
		}
		logging.Warnw("sidecar: fsync failed for tmp file", "tmp", tmpPath, "err", serr, "correlation_id", cid)
		_ = os.Remove(tmpPath)
		return fmt.Errorf("fsync failed for temp file %s: %w", tmpPath, serr)
	}
	if cerr := f.Close(); cerr != nil {
		if lockFile != nil {
			_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
			_ = lockFile.Close()
		}
		logging.Warnw("sidecar: failed to close tmp file", "tmp", tmpPath, "err", cerr, "correlation_id", cid)
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to close temp file %s: %w", tmpPath, cerr)
	}
	if err := os.Rename(tmpPath, path); err != nil {
		if lockFile != nil {
			_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
			_ = lockFile.Close()
		}
		logging.Warnw("sidecar: failed to rename tmp file", "tmp", tmpPath, "final", path, "err", err, "correlation_id", cid)
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to rename temp file %s -> %s: %w", tmpPath, path, err)
	}
	// release lock after successful rename
	if lockFile != nil {
		_ = syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN)
		_ = lockFile.Close()
	}
	logging.Infow("sidecar: saved updates", "path", path, "correlation_id", cid)
	return nil
}
