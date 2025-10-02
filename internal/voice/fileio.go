package voice

import (
	"os"
	"path/filepath"
)

// SaveFileAtomic writes data to path atomically by writing to a tmp file in
// the same directory, fsyncing, closing, and renaming into place.
// mode is the file permission bits (e.g., 0o644).
func SaveFileAtomic(path string, data []byte, mode os.FileMode) error {
	dir := filepath.Dir(path)
	// Ensure directory exists
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
	if err != nil {
		return err
	}
	// write
	if _, err := f.Write(data); err != nil {
		f.Close()
		_ = os.Remove(tmp)
		return err
	}
	// sync to disk
	if err := f.Sync(); err != nil {
		f.Close()
		_ = os.Remove(tmp)
		return err
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	// rename into place
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return err
	}
	return nil
}
