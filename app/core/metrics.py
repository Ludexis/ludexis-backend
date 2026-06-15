from prometheus_client import Counter

auth_login_success_total = Counter(
    "ludexis_auth_login_success_total",
    "Total successful user logins",
)

auth_login_failure_total = Counter(
    "ludexis_auth_login_failure_total",
    "Total failed user logins",
)

library_scans_total = Counter(
    "ludexis_library_scans_total",
    "Total full library scans executed",
)

incremental_scans_total = Counter(
    "ludexis_incremental_scans_total",
    "Total incremental scans executed",
)

metadata_searches_total = Counter(
    "ludexis_metadata_searches_total",
    "Total metadata searches executed",
)

artwork_downloads_total = Counter(
    "ludexis_artwork_downloads_total",
    "Total artwork downloads completed",
)

artwork_downloads_total = Counter(
    "ludexis_artwork_downloads_total",
    "Artwork downloads completed",
)

artwork_validation_failures_total = Counter(
    "ludexis_artwork_validation_failures_total",
    "Artwork validation failures",
)

artwork_deduplications_total = Counter(
    "ludexis_artwork_deduplications_total",
    "Artwork deduplication operations",
)

artwork_auto_download_runs_total = Counter(
    "ludexis_artwork_auto_download_runs_total",
    "Artwork auto-download runs",
)