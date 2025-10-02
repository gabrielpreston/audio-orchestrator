package voice

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// TTSClient performs text->audio synthesis using an external service and
// optionally saves results to disk via SidecarManager.
type TTSClient struct {
	URL       string
	AuthToken string
	Client    *http.Client
	Sidecar   *SidecarManager
	SaveDir   string
	TimeoutMs int
}

// SynthesizeAndSave sends text to the TTS URL, saves returned audio to disk
// if SaveDir is set, and updates the sidecar via SidecarManager. It returns
// the saved filename on success or an error.
func (t *TTSClient) SynthesizeAndSave(text string, ssrc uint32, correlationID string) (string, error) {
	if t == nil || t.URL == "" {
		return "", fmt.Errorf("tts client not configured")
	}
	b2, _ := json.Marshal(map[string]string{"text": text})
	timeout := 10000
	if t.TimeoutMs > 0 {
		timeout = t.TimeoutMs
	}
	resp, err := PostWithRetries(t.Client, t.URL, b2, t.AuthToken, timeout, 2, correlationID)
	if err != nil {
		logging.Debugw("tts: POST failed", "err", err, "correlation_id", correlationID)
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		_, _ = io.ReadAll(resp.Body)
		logging.Warnw("tts: returned non-2xx", "status", resp.StatusCode, "correlation_id", correlationID)
		return "", fmt.Errorf("tts returned status %d", resp.StatusCode)
	}
	audioBytes, rerr := io.ReadAll(resp.Body)
	if rerr != nil {
		logging.Debugw("tts: failed to read response body", "err", rerr, "correlation_id", correlationID)
		return "", rerr
	}
	if t.SaveDir == "" {
		return "", nil
	}
	tsTs := time.Now().UTC().Format("20060102T150405.000Z")
	base := fmt.Sprintf("%s/%s_ssrc%d_tts", strings.TrimRight(t.SaveDir, "/"), tsTs, ssrc)
	fname := base + ".wav"
	tmp := fname + ".tmp"
	if err := os.WriteFile(tmp, audioBytes, 0o644); err != nil {
		logging.Debugw("tts: failed to write tmp file", "err", err, "path", tmp, "correlation_id", correlationID)
		return "", err
	}
	if err := os.Rename(tmp, fname); err != nil {
		logging.Debugw("tts: failed to rename tmp file", "err", err, "tmp", tmp, "final", fname, "correlation_id", correlationID)
		_ = os.Remove(tmp)
		return "", err
	}
	logging.Infow("tts: saved audio to disk", "path", fname, "correlation_id", correlationID)
	if correlationID != "" && t.Sidecar != nil {
		_ = t.Sidecar.MergeUpdatesForCID(correlationID, map[string]interface{}{
			"tts_wav_path":  fname,
			"tts_saved_utc": time.Now().UTC().Format(time.RFC3339Nano),
		})
	}
	return fname, nil
}
