package voice

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/discord-voice-lab/internal/logging"
)

// PostWithRetries posts JSON to url with retry/backoff and returns the response.
// Caller must close resp.Body.
func PostWithRetries(client *http.Client, url string, body []byte, authToken string, timeoutMs int, attempts int, correlationID string) (*http.Response, error) {
	if attempts <= 0 {
		attempts = 1
	}
	for i := 0; i < attempts; i++ {
		ctxReq, cancelReq := context.WithTimeout(context.Background(), time.Duration(timeoutMs)*time.Millisecond)
		req, rerr := http.NewRequestWithContext(ctxReq, "POST", url, bytes.NewReader(body))
		if rerr != nil {
			logging.Debugw("postWithRetries: new request error", "err", rerr, "correlation_id", correlationID)
			cancelReq()
			return nil, rerr
		}
		req.Header.Set("Content-Type", "application/json")
		if authToken != "" {
			req.Header.Set("Authorization", "Bearer "+authToken)
		}

		var resp *http.Response
		var err error
		if client != nil {
			resp, err = client.Do(req)
		} else {
			tmp := &http.Client{Timeout: time.Duration(timeoutMs) * time.Millisecond}
			resp, err = tmp.Do(req)
		}
		cancelReq()
		if err != nil {
			logging.Debugw("postWithRetries: POST attempt failed", "attempt", i+1, "err", err, "correlation_id", correlationID)
			if i < attempts-1 {
				time.Sleep(time.Duration(200*(1<<i)) * time.Millisecond)
				continue
			}
			return nil, err
		}
		return resp, nil
	}
	return nil, fmt.Errorf("no response from postWithRetries")
}
