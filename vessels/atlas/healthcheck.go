// Command healthcheck probes the Atlas dashboard's k8s-style /livez endpoint
// and exits non-zero on failure. It exists because the atlas vessel runs on
// distroless/static (no shell), so the Dockerfile HEALTHCHECK needs a static
// binary — same design the upstream dashboard documents as "out of scope for
// v0.2.x", now solved fleet-side.
package main

import (
	"net/http"
	"os"
	"time"
)

func main() {
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get("http://127.0.0.1:3002/livez")
	if err != nil {
		os.Exit(1)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		os.Exit(1)
	}
}
