import re


class SQLValidationError(Exception):
    pass

FORBIDDEN = ["insert","update","delete","merge","drop","alter","create","truncate"]


def validate_sql(sql: str, semantic: dict | None = None) -> None:
    s = (sql or "").strip()
    if not s:
        raise SQLValidationError("SQL is empty.")

    if not s.upper().startswith("SELECT"):
        raise SQLValidationError("Only SELECT queries are allowed.")

    blocked = ["INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "TRUNCATE ", "MERGE "]
    upper_sql = s.upper()
    for token in blocked:
        if token in upper_sql:
            raise SQLValidationError(f"Blocked SQL operation detected: {token.strip()}")    
