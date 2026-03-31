# Crawler Integration

This guide covers the shared crawling runtime: proxy-profile configuration, source eligibility, transport pools, adaptive path ordering, and critical-source readiness.

## Purpose

- The crawler layer owns proxy transport declarations, transport-pool construction, source-policy filtering, adaptive path ordering, and critical-source readiness checks.
- The app owns which sources are enabled and which sources are product-critical.
- The app owns the source-specific clients built on top of the crawler layer.

## Inputs

- Exact literals:
  - app config keys: `crawler.parallelism`, `crawler.retry_count`, `crawler.http_timeout_seconds`, `crawler.rate_limit_milliseconds`, `crawler.proxy_file`
  - unsupported legacy key: `crawler.proxy_urls`
  - proxy file must be YAML with top-level `proxies:`
  - optional per-source policy key: `source_policies:`
  - browser modes: `direct`, `http_fetch_auth`, `socks_forwarder`
  - source keys modeled in this repo: `tess`, `crunchbase`, `duckduckgo`, `google`, `sec_edgar`
- Files to touch:
  - `.env.example`
  - `configs/config.yaml`
  - `configs/config.localhost.yaml`
  - `configs/proxies.pool.yaml`
  - `internal/config/proxy_profiles.go`
  - `internal/config/config.go`
  - `internal/pipeline/transport_profiles.go`
  - `internal/pipeline/source_path_registry.go`
  - `internal/pipeline/crawler_helpers.go`
  - `cmd/server/main.go`
  - `cmd/server/main_test.go`
  - `internal/pipeline/live_test.go`

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `PROXY_FILE` | app | internal | yes | yes | Path to the YAML proxy-pool file. |
| proxy profiles | crawler runtime | internal | yes | yes | Each proxy declares browser and/or HTTP capability explicitly. |
| `source_policies` | crawler runtime | internal | maybe | maybe | Deny known-bad providers or proxy ids for specific sources. |
| browser transport pool | crawler runtime | internal | yes for browser sources | yes for browser sources | Used by JS-heavy sources. |
| HTTP transport pool | crawler runtime | internal | yes for HTTP sources | yes for HTTP sources | Used by HTML or JSON sources. |
| `SourcePathRegistry` | crawler runtime | internal | yes | yes | Tracks health and reorders eligible paths. |

## Source Of Truth

- `.env.example`
- `README.md`
- `configs/config.yaml`
- `configs/config.localhost.yaml`
- `configs/proxies.pool.yaml`
- `internal/config/proxy_profiles.go`
- `internal/config/config.go`
- `internal/pipeline/transport_profiles.go`
- `internal/pipeline/source_path_registry.go`
- `internal/pipeline/crawler_helpers.go`
- `cmd/server/main.go`
- `cmd/server/main_test.go`
- `internal/pipeline/live_test.go`

## Decision Procedure

1. Add `crawler.proxy_file` to app config and remove `crawler.proxy_urls` from the supported contract.
2. Create a YAML proxy file with top-level `proxies:` entries that declare browser and/or HTTP capability explicitly.
3. If a provider or proxy id is known-bad for one source, add that rule under top-level `source_policies:`.
4. Build one browser transport pool and one HTTP transport pool at startup from the proxy profiles.
5. Create one shared `SourcePathRegistry` and pass it to source clients that participate in health ordering.
6. If some sources are product-critical, gate startup or job admission on critical-source readiness.
7. If no healthy eligible path exists for a required source, fail fast instead of accepting doomed work.

## Minimal Code Or Config Example

```yaml
crawler:
  parallelism: 3
  retry_count: 2
  http_timeout_seconds: 30
  rate_limit_milliseconds: 1000
  proxy_file: "${PROXY_FILE}"
```

```yaml
proxies:
  - id: webshare-us-1
    provider: webshare
    url: http://user:pass@proxy.example.com:80
    browser:
      enabled: true
      mode: http_fetch_auth
      ignore_cert_errors: false
    http:
      enabled: true
      ignore_cert_errors: false

source_policies:
  crunchbase:
    deny_proxy_ids:
      - brightdata-us-1
```

```go
proxyProfiles := applicationConfig.Crawler.ProxyProfiles()
sourcePolicies := applicationConfig.Crawler.SourcePolicies()
browserTransportPool := pipeline.BuildBrowserTransportPool(proxyProfiles, sourcePolicies, applicationConfig.Crawler.RetryCount+1)
httpTransportPool := pipeline.BuildHTTPTransportPool(proxyProfiles, sourcePolicies, applicationConfig.Crawler.RetryCount+1)
sourcePathRegistry := pipeline.NewSourcePathRegistry(time.Now)
```

## Expected Result

- Proxy capability is declared once in YAML instead of being inferred ad hoc.
- Browser and HTTP transport pools exist when the app needs them.
- Ineligible source paths are filtered before requests are attempted.
- Critical-source readiness fails early when no healthy eligible path exists.

## Verification

```bash
# verify startup readiness behavior
go test ./cmd/server -run 'TestEnsureCriticalSourceStartupReady_(FailsWithoutBrowserProfiles|FailsWithoutHTTPProfiles|WrapsMonitorFailure|SucceedsWhenAllCriticalSourcesHaveAHealthyPath)' -count=1

# verify pool building and path ordering behavior
go test ./internal/pipeline -run 'Test(BuildBrowserTransportPool_InterleavesProviders|BuildHTTPTransportPool_UsesOnlyHTTPEnabledProfiles|BuildBrowserTransportPool_PreservesSourceRules|SourcePathRegistry_OrderedHTTPProfiles_SkipsConfigIneligiblePaths|SourcePathRegistry_OrderedBrowserProfiles_PrefersMostRecentlyHealthyPath|SourcePathRegistry_OrderedBrowserProfiles_DeprioritizesProviderBlockedPath)' -count=1

# verify live critical-source acceptance when live proxy configuration exists
go test -tags=live ./internal/pipeline -run TestLive_CriticalSourceAcceptance -count=1 -v
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Startup says no browser or HTTP transport profiles are configured | proxy file is missing, empty, or declares the wrong capabilities | Fix `PROXY_FILE` and ensure the required transport types are enabled. |
| Config rejects the proxy file as legacy | file is plain text or lacks top-level `proxies:` | Convert it to the YAML transport-profile format. |
| One source never becomes healthy even though proxies exist | `source_policies` deny all eligible paths or the provider is externally blocked | Inspect policy and live acceptance output, then change the deny rules intentionally. |
| A browser path works in one env and fails in another | browser mode does not match the proxy URL shape or cert policy | Align `browser.mode` and `ignore_cert_errors` with the real proxy behavior. |

## Stop Rules

- Stop if the proxy source of truth is not a YAML file and cannot be changed.
- Stop if the app cannot say which sources are product-critical.
- Stop if the app wants to infer transport behavior from proxy hostnames instead of explicit profile fields.

## Change Checklist

- [ ] `crawler.proxy_file` is the only proxy source-of-truth path.
- [ ] Proxy profiles declare browser and HTTP capability explicitly.
- [ ] Source-specific deny rules live under top-level `source_policies`.
- [ ] Startup builds shared browser and HTTP pools plus a `SourcePathRegistry`.
- [ ] Critical-source readiness rejects doomed startup or admission paths.
- [ ] Live acceptance covers the required sources.
