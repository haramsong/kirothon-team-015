import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from app.models import InternalInventoryItem


@dataclass(frozen=True)
class DeductionLine:
    item_id: UUID
    use_half_units: int


def canonical_payload_hash(lines: list[DeductionLine]) -> str:
    """품목 ID순 정규 JSON을 SHA-256으로 해시합니다."""
    canonical = [
        {"itemId": str(line.item_id), "useHalfUnits": line.use_half_units}
        for line in sorted(lines, key=lambda line: str(line.item_id))
    ]
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def apply_deduction(
    inventory: list[InternalInventoryItem],
    lines: list[DeductionLine],
) -> tuple[list[InternalInventoryItem], list[str]]:
    """전체 차감 입력을 검증한 뒤 새 재고와 제거 품목명을 반환합니다."""
    if not lines:
        raise ValueError("한 개 이상의 차감 품목이 필요해요.")

    inventory_by_id = {item.id: item for item in inventory}
    if len(inventory_by_id) != len(inventory):
        raise ValueError("재고 품목 ID가 중복되어 있어요.")

    line_ids = [line.item_id for line in lines]
    if len(set(line_ids)) != len(line_ids):
        raise ValueError("같은 품목을 두 번 차감할 수 없어요.")

    deductions = {}
    for line in lines:
        if line.use_half_units < 1:
            raise ValueError("사용 수량은 0.5개 이상이어야 해요.")
        current = inventory_by_id.get(line.item_id)
        if current is None:
            raise ValueError("차감할 재고 품목을 찾을 수 없어요.")
        if line.use_half_units > current.quantity_half_units:
            raise ValueError("사용 수량은 현재 재고보다 많을 수 없어요.")
        deductions[line.item_id] = line.use_half_units

    updated: list[InternalInventoryItem] = []
    removed_names: list[str] = []
    for item in inventory:
        use_half_units = deductions.get(item.id)
        if use_half_units is None:
            updated.append(item.model_copy(deep=True))
            continue
        remaining = item.quantity_half_units - use_half_units
        if remaining == 0:
            removed_names.append(item.name)
        else:
            updated.append(
                item.model_copy(update={"quantity_half_units": remaining}, deep=True)
            )

    return updated, removed_names
