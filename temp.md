                preview = (
            match.content[:100].replace("\n", " ") + "..."
            if len(match.content) > 100
            else match.content.replace("\n", " ")
        )

        table.add_row(
            str(match.file.path),
            str(match.file.ext_kind.language) or "unknown",
            f"{match.relevance_score:.2f}",
            f"{match.span!s}",
            preview,
        )