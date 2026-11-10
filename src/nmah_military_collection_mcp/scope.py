from .errors import RecordScopeError

UNIT_CODE = "NMAH"
RECORD_TYPE = "edanmdm"
SET_NAME_PREFIX = "Military and Society: Armed Forces History"


def build_scope_filters() -> list[str]:
    """Express the same collection scope used to validate detail records."""
    escaped_prefix = SET_NAME_PREFIX.replace(" ", r"\ ").replace(":", r"\:")
    return [
        f"unit_code:{UNIT_CODE}",
        f"type:{RECORD_TYPE}",
        f"set_name:{escaped_prefix}*",
    ]


def validate_record_scope(record: dict, record_id: str) -> None:
    """Reject records whose identity or collection membership cannot be verified."""
    try:
        content = record["content"]
        identity = content["descriptiveNonRepeating"]
        set_names = content["freetext"]["setName"]
        if not isinstance(set_names, list):
            raise ValueError("Unexpected set-name structure.")
        if identity["record_ID"] != record_id:
            raise RecordScopeError("Smithsonian returned a different record ID.")
        if record["unitCode"] != UNIT_CODE or identity["unit_code"] != UNIT_CODE:
            raise RecordScopeError(
                "The requested record is outside the NMAH collection scope."
            )
        if record["type"] != RECORD_TYPE or not any(
            isinstance(item, dict)
            and isinstance(item.get("content"), str)
            and item["content"].startswith(SET_NAME_PREFIX)
            for item in set_names
        ):
            raise RecordScopeError(
                "The requested record is outside the Armed Forces History scope."
            )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RecordScopeError(
            "Smithsonian returned an unverifiable content response structure."
        ) from exc
