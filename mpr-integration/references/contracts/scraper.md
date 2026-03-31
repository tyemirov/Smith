# Scraper Integration

This guide covers the scraping substrate on top of the crawler transport layer: browser rendering, HTTP fetching, parsing, challenge detection, and source-client result semantics.

## Purpose

- The scraper layer owns browser-backed rendering, HTTP-backed fetching, shared parsing helpers, and explicit failure classification.
- The app owns source-specific selectors, query flows, and business interpretation of source results.
- The app owns which sources are critical enough to affect health or admission.

## Inputs

- Exact literals:
  - browser transport type: `BrowserTransport`
  - browser session type: `BrowserSession`
  - HTTP transport type: `HTTPTransport`
  - rendering boundary: `PageRenderer`
  - parse boundary: `HTMLParser`
  - critical statuses: `transport_timeout`, `proxy_auth_failed`, `tls_failed`, `provider_blocked`, `site_challenge`, `search_not_executed`, `parse_failed`, `success_no_results`, `success_results_found`
  - browser-backed sources in this repo: `tess`, `crunchbase`, `google`
  - HTTP-backed sources in this repo: `duckduckgo`, `sec_edgar`
- Files to touch:
  - `internal/pipeline/browser_transport.go`
  - `internal/pipeline/crawler_helpers.go`
  - `internal/pipeline/transport_profiles.go`
  - `internal/pipeline/tess_jseval.go`
  - `internal/pipeline/crunchbase_jseval.go`
  - `internal/pipeline/google_jseval.go`
  - `internal/pipeline/duckduckgo.go`
  - `internal/pipeline/sec_edgar.go`
  - `internal/pipeline/live_test.go`

| Input | Consumed by | Type | Required locally | Required when hosted | Notes |
| --- | --- | --- | --- | --- | --- |
| `BrowserTransportProfile` | browser-backed sources | internal | yes for JS-heavy sources | yes for JS-heavy sources | Carries browser mode, proxy URL, cert policy, and source rules. |
| `HTTPTransportProfile` | HTTP-backed sources | internal | yes for HTTP sources | yes for HTTP sources | Carries proxy URL, cert policy, and source rules. |
| `PageRenderer` | browser-backed sources | internal | yes for browser sources | yes for browser sources | Production uses the real JS evaluation path. |
| `HTMLParser` | source clients | internal | yes | yes | Production uses `goquery`. |
| `CriticalAttemptError` | sources + health logic | internal | yes | yes | Stable failure classification boundary. |

## Source Of Truth

- `internal/pipeline/browser_transport.go`
- `internal/pipeline/crawler_helpers.go`
- `internal/pipeline/transport_profiles.go`
- `internal/pipeline/tess_jseval.go`
- `internal/pipeline/crunchbase_jseval.go`
- `internal/pipeline/google_jseval.go`
- `internal/pipeline/duckduckgo.go`
- `internal/pipeline/sec_edgar.go`
- `internal/pipeline/live_test.go`

## Decision Procedure

1. Decide whether the new source is browser-backed or HTTP-backed before writing source logic.
2. Accept ordered transport profiles from the shared crawler layer instead of inventing source-local proxy logic.
3. If the source is browser-backed, use `BrowserTransport.RenderPage(...)` or a session-backed searcher.
4. Else if the source is HTTP-backed, build a client through `HTTPTransport.NewClient(...)`.
5. Parse HTML with `goquery` or parse JSON directly, but keep parse failure explicit.
6. If the remote site returns a block, challenge, or incomplete search flow, return an explicit `CriticalAttemptError` instead of empty success.
7. If the source participates in health ordering, record attempts and successes in `SourcePathRegistry`.

## Minimal Code Or Config Example

```go
renderResult, renderError := browserTransport.RenderPage(
    ctx,
    searchURL,
    transportProfile,
    timeout,
    ".search-results, body",
    "Mozilla/5.0 ...",
)
```

```go
httpClient, clientError := httpTransport.NewClient(transportProfile, timeout)
response, responseError := httpClient.Do(request)
```

```go
return &CriticalAttemptError{
    SourceKey:   "crunchbase",
    TransportID: transportProfile.ID,
    Provider:    transportProfile.Provider,
    Status:      CriticalAttemptStatusSiteChallenge,
    Detail:      "crunchbase returned Cloudflare block",
}
```

## Expected Result

- Each source chooses browser or HTTP transport explicitly.
- Source code uses shared transport profiles instead of hardcoded proxy logic.
- Success, no-results, parse-failure, and challenge/block outcomes are explicit.
- Critical sources feed path-health data back into the crawler layer.

## Verification

```bash
# verify source constructors and explicit source semantics
go test ./internal/pipeline -run 'Test(NewDuckDuckGoClient_WithTransportPool|SECEdgarChecker_CheckCompanyFilings_HasFilings|TESSClient_CheckTrademark_ResultsFound|CrunchbaseClient_CheckCompany_CompanyFound|GoogleSearchClient_SearchBrand_WithResults|DuckDuckGo_BotDetection_Unit)' -count=1

# verify live source behavior when live transport config exists
go test -tags=live ./internal/pipeline -run 'TestLive_(SECEdgar_TableDriven|DuckDuckGo_BotDetection|DuckDuckGo_TableDriven|TESS_TableDriven|Crunchbase_TableDriven)' -count=1 -v
```

## Failure Map

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Scraper returns empty success on a blocked page | challenge or block markers are not detected | Add explicit challenge/provider-block detection and return `CriticalAttemptError`. |
| A source works only with one hardcoded proxy | the source bypassed shared transport profiles | Route the source through the shared browser or HTTP transport pool. |
| Browser source never executes the actual search | wait selector, submit flow, or final-request detection is wrong | Add explicit `search_not_executed` handling and fix the browser flow. |
| HTTP source is flaky across providers | path health or source policy is not being recorded and applied | Integrate with `SourcePathRegistry` and source eligibility rules. |

## Stop Rules

- Stop if the source type is unknown and no one can answer whether it needs browser or HTTP transport.
- Stop if the source must bypass the shared crawler transport layer.
- Stop if the app wants to treat challenge or block pages as successful empty results.

## Change Checklist

- [ ] The source chooses browser or HTTP transport explicitly.
- [ ] The source consumes shared transport profiles.
- [ ] Challenge, provider-block, parse-failure, and no-results outcomes are explicit.
- [ ] Critical sources report path health through `SourcePathRegistry`.
- [ ] Live acceptance exists when the source depends on real remote behavior.
