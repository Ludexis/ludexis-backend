from app.schemas.metadata import MetadataDetails

class MetadataConflictResolver:
    
    def resolve(self, primary: MetadataDetails, secondary: MetadataDetails | None = None,) -> MetadataDetails:
        if secondary is None:
            return primary

        return MetadataDetails(
            provider=primary.provider,
            provider_id=primary.provider_id,

            title=self._pick_best_text(
                primary.title,
                secondary.title,
            ),

            description=self._pick_best_text(
                primary.description,
                secondary.description,
            ),

            release_date=(
                primary.release_date
                or secondary.release_date
            ),

            genres=self._merge_unique(
                primary.genres,
                secondary.genres,
            ),

            developers=self._merge_companies(
                primary.developers,
                secondary.developers,
            ),

            publishers=self._merge_companies(
                primary.publishers,
                secondary.publishers,
            ),

            tags=self._merge_unique(
                primary.tags,
                secondary.tags,
            ),

            artwork_urls=list(
                dict.fromkeys(
                    secondary.artwork_urls
                    + primary.artwork_urls
                )
            ),
        )
    def _pick_best_text(
        self,
        primary: str | None,
        secondary: str | None,
    ) -> str | None:
        return primary or secondary


    def _merge_unique(
        self,
        primary: list[str],
        secondary: list[str],
    ) -> list[str]:
        return sorted(
            set(primary) | set(secondary)
        )

    def _normalize_company(
        self,
        name: str,
    ) -> str:

        name = name.strip()
        replacements = {
            "SEGA": "Sega",
            "CREATIVE ASSEMBLY": "The Creative Assembly",
            "Wube Software LTD.": "Wube Software",
            "VALVE CORPORATION": "Valve",
            "Valve Corporation": "Valve",
        }

        return replacements.get(
            name,
            name,
        )
    def _merge_companies(
        self,
        primary: list[str],
        secondary: list[str],
    ) -> list[str]:

        companies = {}

        for company in (
            primary + secondary
        ):
            normalized = (
                self._normalize_company(
                    company
                )
            )

            companies[
                normalized.lower()
            ] = normalized

        return sorted(
            companies.values()
        )