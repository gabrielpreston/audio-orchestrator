package voice

import (
	"context"
	"encoding/json"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// StartSaveAudioCleaner starts a background goroutine that periodically
// scans dir for sidecar JSON files and their paired wavs, removing entries
// older than retention and enforcing maxFiles. Caller must call wg.Add(1)
// before calling this function; the goroutine will call wg.Done() on exit.
func StartSaveAudioCleaner(ctx context.Context, wg *sync.WaitGroup, dir string, retention time.Duration, interval time.Duration, maxFiles int) {
	go func() {
		defer wg.Done()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				files, err := os.ReadDir(dir)
				if err != nil {
					logging.Debugw("saveaudio: cleanup readDir failed", "err", err)
					continue
				}
				type pairInfo struct {
					jsonPath string
					wavPath  string
					mod      time.Time
				}
				pairs := make(map[string]*pairInfo)
				for _, fi := range files {
					name := fi.Name()
					if !strings.HasSuffix(name, ".json") {
						continue
					}
					jsonPath := dir + "/" + name
					b, err := os.ReadFile(jsonPath)
					if err != nil {
						continue
					}
					var sc map[string]interface{}
					if err := json.Unmarshal(b, &sc); err != nil {
						continue
					}
					wavPath := ""
					if v, ok := sc["wav_path"].(string); ok && v != "" {
						wavPath = v
					} else {
						wavPath = strings.TrimSuffix(jsonPath, ".json") + ".wav"
					}
					st, err := os.Stat(jsonPath)
					if err != nil {
						continue
					}
					base := strings.TrimSuffix(name, ".json")
					pairs[base] = &pairInfo{jsonPath: jsonPath, wavPath: wavPath, mod: st.ModTime()}
				}
				var pairList []pairInfo
				for _, p := range pairs {
					pairList = append(pairList, *p)
				}
				sort.Slice(pairList, func(i, j int) bool { return pairList[i].mod.Before(pairList[j].mod) })
				cutoff := time.Now().Add(-retention)
				removed := 0
				for _, pi := range pairList {
					if pi.mod.Before(cutoff) {
						_ = os.Remove(pi.jsonPath)
						if pi.wavPath != "" {
							_ = os.Remove(pi.wavPath)
						}
						removed++
					}
				}
				if maxFiles > 0 {
					filesLeft := len(pairList) - removed
					if filesLeft > maxFiles {
						toRemove := filesLeft - maxFiles
						count := 0
						for _, pi := range pairList {
							if count >= toRemove {
								break
							}
							if _, err := os.Stat(pi.jsonPath); err == nil {
								_ = os.Remove(pi.jsonPath)
							}
							if pi.wavPath != "" {
								if _, err := os.Stat(pi.wavPath); err == nil {
									_ = os.Remove(pi.wavPath)
								}
							}
							count++
						}
					}
				}
			}
		}
	}()
}
