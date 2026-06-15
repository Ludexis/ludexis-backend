# ✅~~Backlog~~

## ✅~~Authentication & Authorization~~

### ✅~~High Priority~~

- ✅~~Fix Swagger OAuth2 integration mismatch (Swagger expects OAuth2 Password Flow form data while backend login endpoint currently accepts JSON payloads).~~
- ✅~~Replace development JWT secret with a generated production-grade secret.~~
- Replace all development credentials and example secrets before public releases.
- ✅~~Review and stabilize bcrypt/passlib dependency versions to prevent compatibility regressions.~~
  - ~~passlib==1.7.4~~
  - ~~bcrypt==4.0.1~~
  - ~~bcrypt >=5.0.0 is incompatible with passlib 1.7.4 and breaks authentication.~~
- ✅~~Add automated integration tests for authentication, token refresh, logout, and authorization flows.~~

### ✅~~Low Priority~~

- ✅~~Improve Swagger authorization experience for protected endpoints.~~
- ✅~~Add token expiration and refresh workflow tests.~~

---

## ✅~~Security & RBAC~~

### ✅~~High Priority~~

- ✅~~Seed default permissions during system initialization.~~
- ✅~~Seed default roles during system initialization.~~
- ✅~~Seed default role-permission mappings during system initialization.~~
- ✅~~Create administrator role automatically during first-time setup.~~
- ✅~~Validate permission enforcement across all protected endpoints.~~

### ✅~~Medium Priority~~

- ✅~~Add permission audit reporting.~~
- ✅~~Expand audit logging coverage for administrative actions.~~

---

## ✅~~Metadata & Enrichment~~

### ✅~~High Priority~~

- ✅~~Implement IGDB provider integration.~~
- ✅~~Implement Steam metadata provider.~~
- ❌~~Implement GOG metadata provider (deferred, not as complete as Steam or IGDB, and changing endpoints).~~
- ✅~~Implement automatic metadata matching workflow.~~
- ✅~~Implement metadata refresh jobs.~~
- ✅~~Implement Genre/Developer/Publisher Synchronization.~~

### ✅~~Medium Priority~~

- ✅~~Metadata confidence scoring.~~
- ✅~~Metadata conflict resolution.~~
- ✅~~Multi-provider metadata merging.~~
- ✅~~Manual metadata override workflow.~~

### ✅~~Low Priority~~

- ✅~~IGDB's involved_companies flags mapping involved_companies.company.name into both developers & publishers.~~
- ✅~~Entity normalization, IGDB: The Creative Assembly and Steam: CREATIVE ASSEMBLY.~~

---

## ✅~~Artwork System~~

### ✅~~High Priority~~

- ✅~~Implement artwork download pipeline.~~
- ✅~~Implement artwork validation jobs.~~
- ✅~~Self-healing artwork refresh.~~
- ✅~~Automatic cover selection.~~

### ✅~~Medium Priority~~

- ✅~~Automatic Banner/Logo download.~~
- ✅~~Screenshot importing.~~
- ✅~~Artwork quality scoring.~~
- ✅~~Artwork deduplication.~~
- ✅~~Implement local artwork caching and storage management in dedicated directory.~~

---

## ✅~~Archive Management~~

### ✅~~High Priority~~

- ✅~~Fix `ArchiveEntryRead` serialization inconsistencies.~~
  - ~~Relationship data is returned correctly.~~
  - ~~`tag_ids`~~
  - ~~`developer_ids`~~
  - ~~`publisher_ids`~~
  - ~~`collection_ids`~~
    ~~currently return empty arrays despite valid relationships existing.~~

### ✅~~Medium Priority~~

- ✅~~Improve filename normalization.~~
- ✅~~Improve version detection from filenames.~~
- ✅~~Improve archive naming heuristics.~~
- ✅~~Duplicate archive detection.~~
- ✅~~Multi-library support.~~

---

## ✅~~Scanner & Ingestion~~

### ✅~~Planned~~

- ✅~~File Metadata Foundation.~~
- ✅~~Archive hash generation.~~
- ✅~~Incremental scan optimization.~~
- ✅~~Archive integrity verification.~~
- ✅~~File move/rename detection.~~

### ✅~~Low Priority~~

- ✅~~Reuse hash instead of recalculating at every scan.~~
- ✅~~`get_all_by_hash()` duplicate detection.~~
- ❌~~Parallel scan execution (deferred, not needed unless library size is extremely large, also hardware might bottleneck).~~

---

## ✅~~Background Jobs~~

### ✅~~Planned~~

- ✅~~Job retry policies.~~
- ✅~~Scheduled metadata refreshes.~~
- ✅~~Scheduled artwork validation.~~
- ✅~~Celery Beat for scheduling.~~
- ✅~~Job queue monitoring endpoints.~~
- ✅~~Job cancellation improvements.~~

---

## ✅~~API & Documentation~~

### ✅~~High Priority~~

- ✅~~Fix Swagger OAuth2 flow compatibility.~~

### ✅~~Medium Priority~~

- ✅~~Improve OpenAPI examples.~~
- ✅~~Expand endpoint documentation.~~
- ✅~~Add API usage guides.~~
- ✅~~Add developer integration examples.~~

---

## ✅~~Infrastructure~~

### ✅~~Medium Priority~~

- ✅~~Move all runtime configuration fully into environment variables.~~
- ✅~~Remove remaining hardcoded development defaults.~~
- ✅~~Review Docker production deployment configuration.~~
- ✅~~Add CI/CD validation pipeline.~~

### ✅~~Low Priority~~

- ✅~~Health check endpoints.~~
- ✅~~Metrics and monitoring integration.~~
- ✅~~Structured logging improvements.~~

---

## ✅~~Testing~~

### ✅~~High Priority~~

- ✅~~Authentication integration tests.~~
- ✅~~RBAC integration tests.~~
- ✅~~Permission enforcement across all protected endpoints.~~
- ✅~~Scanner integration tests.~~
- ✅~~Metadata provider tests.~~
- ✅~~Background job tests.~~
- ✅~~End-to-end API test suite.~~
