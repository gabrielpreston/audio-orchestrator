package voice

import (
	"regexp"
	"strings"
)

// WakeDetector encapsulates wake-phrase detection configuration.
type WakeDetector struct {
	Phrases []string
	WindowS int
}

func NewWakeDetector(phrases []string, windowS int) *WakeDetector {
	return &WakeDetector{Phrases: phrases, WindowS: windowS}
}

// Detect returns (matched, stripped). 'stripped' is the text after removing
// the detected wake phrase, or empty when none matched.
func (w *WakeDetector) Detect(text string) (bool, string) {
	if text == "" {
		return false, ""
	}
	s := strings.ToLower(strings.TrimSpace(text))
	s = regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")
	s = strings.TrimLeft(s, " \t\n\r\f\v\"'`~")
	windowS := w.WindowS
	for _, wp := range w.Phrases {
		if wp == "" {
			continue
		}
		if s == wp {
			return true, ""
		}
		if windowS == 0 {
			prefixes := []string{wp + " ", wp + ",", wp + ".", wp + "!", wp + "?", wp + ":"}
			for _, pref := range prefixes {
				if strings.HasPrefix(s, pref) {
					stripped := strings.TrimLeft(strings.TrimSpace(s[len(pref):]), " ,.!?;:-\"'`~")
					return true, stripped
				}
			}
			continue
		}
		words := strings.Fields(s)
		k := windowS * 3
		if k < 3 {
			k = 3
		}
		if len(words) > k {
			words = words[:k]
		}
		wpWords := strings.Fields(wp)
		if len(wpWords) == 0 {
			continue
		}
		normalizeToken := func(tok string) string {
			return strings.Trim(strings.ToLower(strings.TrimSpace(tok)), " ,.!?;:-\"'`~")
		}
		for i := 0; i+len(wpWords) <= len(words); i++ {
			match := true
			for j := 0; j < len(wpWords); j++ {
				if normalizeToken(words[i+j]) != normalizeToken(wpWords[j]) {
					match = false
					break
				}
			}
			if match {
				fullWords := strings.Fields(strings.TrimSpace(regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")))
				foundIdx := -1
				for fi := 0; fi+len(wpWords) <= len(fullWords); fi++ {
					okMatch := true
					for fj := 0; fj < len(wpWords); fj++ {
						if normalizeToken(fullWords[fi+fj]) != normalizeToken(wpWords[fj]) {
							okMatch = false
							break
						}
					}
					if okMatch {
						foundIdx = fi
						break
					}
				}
				stripped := ""
				if foundIdx >= 0 && foundIdx+len(wpWords) <= len(fullWords) {
					if foundIdx+len(wpWords) < len(fullWords) {
						stripped = strings.Join(fullWords[foundIdx+len(wpWords):], " ")
						stripped = strings.Trim(stripped, " ,.!?;:-\"'`~")
					}
				}
				return true, stripped
			}
		}
	}
	return false, ""
}
