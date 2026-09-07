FORBIDDEN_TOKENS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
}


def validate_sql(sql: str) -> bool:
    normalized = sql.upper()
    return not any(token in normalized for token in FORBIDDEN_TOKENS)

