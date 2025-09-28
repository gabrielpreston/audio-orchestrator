package llm

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

type Client struct {
	BaseURL string
	APIKey  string
	HTTP    *http.Client
}

type ChatRequest struct {
	Model       string   `json:"model,omitempty"`
	Messages    []string `json:"messages,omitempty"`
	MaxTokens   int      `json:"max_tokens,omitempty"`
	Temperature float64  `json:"temperature,omitempty"`
}

type ChatResponse struct {
	ID      string `json:"id,omitempty"`
	Content string `json:"content,omitempty"`
}

var (
	ErrPermanent = errors.New("permanent error")
	ErrTransient = errors.New("transient error")
)

func NewClientFromEnv() *Client {
	base := os.Getenv("OPENAI_BASE_URL")
	key := os.Getenv("OPENAI_API_KEY")
	if base == "" {
		base = "http://127.0.0.1:8000/v1"
	}
	return &Client{
		BaseURL: strings.TrimRight(base, "/"),
		APIKey:  key,
		HTTP:    &http.Client{Timeout: 20 * time.Second},
	}
}

func (c *Client) CreateChatCompletion(ctx context.Context, req ChatRequest) (ChatResponse, error) {
	// resolve model
	gpt5Enabled := strings.ToLower(os.Getenv("GPT5_ENABLED"))
	defaultModel := os.Getenv("OPENAI_MODEL")
	fallback := os.Getenv("OPENAI_FALLBACK_MODEL")
	model := req.Model
	if model == "" {
		if gpt5Enabled == "false" {
			model = fallback
		} else {
			model = defaultModel
		}
	}
	if model == "" {
		model = "local"
	}

	// enforce limits
	maxTokens := req.MaxTokens
	if maxTokens <= 0 {
		maxTokens = 512
	}
	// clamp
	cfgMax := 4000
	if mt := os.Getenv("LLM_MAX_TOKENS"); mt != "" {
		var parsed int
		fmt.Sscanf(mt, "%d", &parsed)
		if parsed > 0 {
			cfgMax = parsed
		}
	}
	if maxTokens > cfgMax {
		maxTokens = cfgMax
	}

	// prepare payload
	payload := map[string]interface{}{
		"model":       model,
		"messages":    req.Messages,
		"max_tokens":  maxTokens,
		"temperature": req.Temperature,
	}
	bodyBytes, _ := json.Marshal(payload)

	url := fmt.Sprintf("%s/chat/completions", c.BaseURL)
	httpReq, _ := http.NewRequestWithContext(ctx, "POST", url, strings.NewReader(string(bodyBytes)))
	httpReq.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+c.APIKey)
	}

	resp, err := c.HTTP.Do(httpReq)
	if err != nil {
		// transient network error; try fallback once if different
		if fallback != "" && fallback != model {
			return c.callFallback(ctx, req, fallback)
		}
		return ChatResponse{}, fmt.Errorf("%w: %v", ErrTransient, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		var out struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
			return ChatResponse{}, fmt.Errorf("%w: decode error: %v", ErrTransient, err)
		}
		content := ""
		if len(out.Choices) > 0 {
			content = out.Choices[0].Message.Content
		}
		return ChatResponse{ID: "resp", Content: content}, nil
	}

	// classify errors
	if resp.StatusCode >= 500 || resp.StatusCode == 429 {
		// transient server errors -> try fallback
		if fallback != "" && fallback != model {
			return c.callFallback(ctx, req, fallback)
		}
		return ChatResponse{}, fmt.Errorf("%w: status %d", ErrTransient, resp.StatusCode)
	}

	// 4xx are treated as permanent
	return ChatResponse{}, fmt.Errorf("%w: status %d", ErrPermanent, resp.StatusCode)
}

func (c *Client) callFallback(ctx context.Context, req ChatRequest, fallback string) (ChatResponse, error) {
	// quick retry using fallback model
	req.Model = fallback
	// small backoff
	time.Sleep(250 * time.Millisecond)
	// prepare payload
	payload := map[string]interface{}{
		"model":       req.Model,
		"messages":    req.Messages,
		"max_tokens":  req.MaxTokens,
		"temperature": req.Temperature,
	}
	bodyBytes, _ := json.Marshal(payload)
	url := fmt.Sprintf("%s/chat/completions", c.BaseURL)
	httpReq, _ := http.NewRequestWithContext(ctx, "POST", url, strings.NewReader(string(bodyBytes)))
	httpReq.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+c.APIKey)
	}
	resp, err := c.HTTP.Do(httpReq)
	if err != nil {
		return ChatResponse{}, fmt.Errorf("%w: fallback network error: %v", ErrTransient, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		var out struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
			return ChatResponse{}, fmt.Errorf("%w: decode error: %v", ErrTransient, err)
		}
		content := ""
		if len(out.Choices) > 0 {
			content = out.Choices[0].Message.Content
		}
		return ChatResponse{ID: "resp-fallback", Content: content}, nil
	}
	if resp.StatusCode >= 500 || resp.StatusCode == 429 {
		return ChatResponse{}, fmt.Errorf("%w: fallback status %d", ErrTransient, resp.StatusCode)
	}
	return ChatResponse{}, fmt.Errorf("%w: fallback status %d", ErrPermanent, resp.StatusCode)
}
