from decimal import Decimal, ROUND_HALF_UP


def measurement_to_half_units(amount: Decimal, sale_unit: Decimal) -> int:
    """측정량을 판매 단위로 나누고 가장 가까운 반 개 단위로 반올림합니다."""
    if amount <= 0 or sale_unit <= 0:
        raise ValueError("측정량과 판매 단위는 0보다 커야 합니다.")

    item_count = amount / sale_unit
    return int((item_count * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def quantity_to_half_units(quantity: Decimal | float | int) -> int:
    """0.5개 배수인 외부 수량을 내부 반 개 단위 정수로 변환합니다."""
    decimal_quantity = Decimal(str(quantity))
    half_units = decimal_quantity * 2
    if decimal_quantity < Decimal("0.5") or half_units != half_units.to_integral_value():
        raise ValueError("수량은 0.5개 이상의 0.5개 배수여야 합니다.")
    return int(half_units)


def half_units_to_quantity(half_units: int) -> float:
    """내부 반 개 단위 정수를 외부 개수 수량으로 변환합니다."""
    if half_units < 1:
        raise ValueError("반 개 단위 수량은 1 이상이어야 합니다.")
    return half_units / 2
