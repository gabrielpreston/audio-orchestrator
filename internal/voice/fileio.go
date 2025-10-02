package voice

import (
	"os"
	"path/filepath"

	"github.com/discord-voice-lab/internal/logging"
)

// SaveFileAtomic writes data to path atomically by writing to a tmp file in
// the same directory, fsyncing, closing, and renaming into place.
// mode is the file permission bits (e.g., 0o644).
func SaveFileAtomic(path string, data []byte, mode os.FileMode) error {
	dir := filepath.Dir(path)
	// Ensure directory exists
	if err := os.MkdirAll(dir, 0o755); err != nil {
		logging.Warnw("savefile: mkdirall failed", "dir", dir, "err", err)
		return err
	}
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
	if err != nil {
		logging.Warnw("savefile: open tmp failed", "tmp", tmp, "err", err)
		return err
	}
	// write
	if _, err := f.Write(data); err != nil {
		f.Close()
		_ = os.Remove(tmp)
		logging.Warnw("savefile: write failed", "tmp", tmp, "err", err)
		return err
	}
	// sync to disk
	if err := f.Sync(); err != nil {
		f.Close()
		_ = os.Remove(tmp)
		logging.Warnw("savefile: fsync failed", "tmp", tmp, "err", err)
		return err
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmp)
		logging.Warnw("savefile: close tmp failed", "tmp", tmp, "err", err)
		return err
	}
	// rename into place
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		logging.Warnw("savefile: rename failed", "tmp", tmp, "final", path, "err", err)
		return err
	}
	return nil
}
