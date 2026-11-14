from collections.abc import Iterable
from datetime import date

from app.models import InternalInventoryItem

MAX_INVENTORY_ITEMS = 200


def merge_inventory_items(
    existing: Iterable[InternalInventoryItem],
    incoming: Iterable[InternalInventoryItem],
) -> list[InternalInventoryItem]:
    """정확히 같은 이름을 기존 항목에 병합하고 기존 ID와 보관 위치를 유지합니다."""
    merged = [item.model_copy(deep=True) for item in existing]
    index_by_name = {item.name: index for index, item in enumerate(merged)}

    for candidate in incoming:
        index = index_by_name.get(candidate.name)
        if index is None:
            index_by_name[candidate.name] = len(merged)
            merged.append(candidate.model_copy(deep=True))
            continue

        current = merged[index]
        expiration_date = min(current.expiration_date, candidate.expiration_date)
        if current.expiration_date < candidate.expiration_date:
            expiration_estimated = current.expiration_estimated
        elif candidate.expiration_date < current.expiration_date:
            expiration_estimated = candidate.expiration_estimated
        else:
            expiration_estimated = (
                current.expiration_estimated and candidate.expiration_estimated
            )

        merged[index] = current.model_copy(
            update={
                "quantity_half_units": (
                    current.quantity_half_units + candidate.quantity_half_units
                ),
                "expiration_date": expiration_date,
                "expiration_estimated": expiration_estimated,
            }
        )

    if len(merged) > MAX_INVENTORY_ITEMS:
        raise ValueError(f"재고 품목은 최대 {MAX_INVENTORY_ITEMS}개까지 저장할 수 있습니다.")
    return merged


def sort_inventory_items(
    items: Iterable[InternalInventoryItem], today: date
) -> list[InternalInventoryItem]:
    """지난 품목을 먼저 두고 각 그룹을 소비기한 오름차순으로 정렬합니다."""
    return sorted(
        items,
        key=lambda item: (
            0 if item.expiration_date < today else 1,
            item.expiration_date,
            item.name,
            str(item.id),
        ),
    )
