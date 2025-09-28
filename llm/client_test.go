package llm

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestModelSelectionAndFallback(t *testing.T) {
	// mock server that returns 500 for model "gpt-5" and 200 for others
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var p map[string]interface{}
		json.NewDecoder(r.Body).Decode(&p)
		model, _ := p["model"].(string)
		if model == "gpt-5" {
			http.Error(w, "server error", 500)
			return
		}
		resp := map[string]interface{}{"choices": []map[string]interface{}{{"message": map[string]string{"content": "ok from " + model}}}}
		json.NewEncoder(w).Encode(resp)
	}))
	defer ts.Close()

	os.Setenv("OPENAI_BASE_URL", ts.URL)
	os.Setenv("OPENAI_MODEL", "gpt-5")
	os.Setenv("OPENAI_FALLBACK_MODEL", "local")
	os.Setenv("GPT5_ENABLED", "true")

	client := NewClientFromEnv()
	// success path: fallback should be used
	resp, err := client.CreateChatCompletion(context.Background(), ChatRequest{Messages: []string{"hello"}})
	if err != nil {
		t.Fatalf("expected success via fallback, got err: %v", err)
	}
	if resp.Content != "ok from local" {
		t.Fatalf("unexpected content: %v", resp.Content)
	}
}

func TestPermanentError(t *testing.T) {
	// mock server that returns 401 for any request
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "unauthorized", 401)
	}))
	defer ts.Close()

	os.Setenv("OPENAI_BASE_URL", ts.URL)
	os.Setenv("OPENAI_MODEL", "gpt-5")
	os.Setenv("OPENAI_FALLBACK_MODEL", "local")
	os.Setenv("GPT5_ENABLED", "true")

	client := NewClientFromEnv()
	_, err := client.CreateChatCompletion(context.Background(), ChatRequest{Messages: []string{"hi"}})
	if err == nil {
		t.Fatalf("expected an error")
	}
	if !isPermanent(err) {
		t.Fatalf("expected permanent error, got: %v", err)
	}
}

func isPermanent(err error) bool {
	if err == nil {
		return false
	}
	if err.Error() == ErrPermanent.Error() {
		return true
	}
	if len(err.Error()) >= 9 && err.Error()[:9] == "permanent" {
		return true
	}
	return false
}
