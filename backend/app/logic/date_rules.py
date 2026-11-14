from datetime import date, timedelta


def parse_iso_date(value: str) -> date:
    """YYYY-MM-DD 형식의 실제 달력 날짜를 반환합니다."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("소비기한은 유효한 YYYY-MM-DD 날짜여야 합니다.") from error
    if parsed.isoformat() != value:
        raise ValueError("소비기한은 유효한 YYYY-MM-DD 날짜여야 합니다.")
    return parsed


def estimate_expiration_date(
    request_date: date,
    shelf_life_days: int,
    detected_purchase_date: date | None = None,
) -> tuple[date, bool]:
    """감지 구매일 또는 요청일에 보관 기간을 더해 예상 소비기한을 만듭니다."""
    if shelf_life_days < 0:
        raise ValueError("보관 기간은 0일 이상이어야 합니다.")
    base_date = detected_purchase_date or request_date
    return base_date + timedelta(days=shelf_life_days), True
