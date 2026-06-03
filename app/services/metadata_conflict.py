from app.schemas.metadata import MetadataDetails

class MetadataConflictResolver:
    def resolve(self, primary: MetadataDetails, secondary: MetadataDetails | None = None,) -> MetadataDetails:
        if secondary is None:
            return primary

        return MetadataDetails(
            provider=primary.provider,
            provider_id=primary.provider_id,

            title=primary.title or secondary.title,

            description=(
                primary.description
                or secondary.description
            ),

            release_date=(
                primary.release_date
                or secondary.release_date
            ),

            genres=sorted(
                set(primary.genres)
                | set(secondary.genres)
            ),

            developers=sorted(
                set(primary.developers)
                | set(secondary.developers)
            ),

            publishers=sorted(
                set(primary.publishers)
                | set(secondary.publishers)
            ),

            tags=sorted(
                set(primary.tags)
                | set(secondary.tags)
            ),

            artwork_urls=list(
                dict.fromkeys(
                    primary.artwork_urls
                    + secondary.artwork_urls
                )
            ),
        )