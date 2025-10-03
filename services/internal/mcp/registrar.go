package mcp

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

// Register posts a simple service record to the MCP register endpoint.
func Register(name, url string) error {
	mcp := os.Getenv("MCP_URL")
	if mcp == "" {
		return nil
	}
	rec := map[string]string{"name": name, "url": url}
	b, _ := json.Marshal(rec)
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Post(mcp+"/mcp/register", "application/json", bytes.NewReader(b))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("mcp register failed: %s", resp.Status)
	}
	log.Printf("registered %s with mcp %s", name, mcp)
	return nil
}
