"""
Перевіряє РЕАЛЬНУ структуру відповідей tonnelmp, перш ніж ми зав'яжемо на неї
логіку арбітражу (той самий підхід, що і з aportalsmp - без здогадок).

Як отримати authData для Tonnel (інакше, ніж для Portals!):
1. Відкрий міні-апку Tonnel (https://market.tonnel.network/) через Telegram
   або в браузері після логіну.
2. DevTools (F12) -> вкладка Application -> Storage -> Local Storage ->
   https://market.tonnel.network/
3. Знайди ключ "web-initData" -> скопіюй значення поруч з ним ПОВНІСТЮ.

Використання:
    python inspect_tonnel.py "ТВІЙ_web-initData_ТУТ" "Toy Bear"
"""
from __future__ import annotations

import json
import sys

from tonnelmp import filterStatsPretty, getGifts, getAuctions

_PRIMITIVES = (str, int, float, bool, type(None))


def _summarize(value, depth: int = 0):
    if isinstance(value, _PRIMITIVES):
        return value
    if isinstance(value, (list, tuple)):
        return [_summarize(v, depth + 1) for v in value[:3]] + (
            ["..."] if len(value) > 3 else []
        )
    if isinstance(value, dict):
        items = list(value.items())
        if depth == 0 and len(items) > 5:
            preview = {k: _summarize(v, depth + 1) for k, v in items[:5]}
            preview["...total_keys..."] = len(items)
            return preview
        return {k: _summarize(v, depth + 1) for k, v in items}
    if hasattr(value, "__dict__"):
        return {k: _summarize(v, depth + 1) for k, v in vars(value).items()}
    return str(value)


def main() -> None:
    if len(sys.argv) < 2:
        print('Використання: python inspect_tonnel.py "web-initData" ["назва подарунка"]')
        return

    auth = sys.argv[1]
    gift_name = sys.argv[2] if len(sys.argv) > 2 else "Toy Bear"

    print("=" * 60)
    print("== filterStatsPretty(authData) ==")
    try:
        stats = filterStatsPretty(authData=auth)
        print(json.dumps(_summarize(stats), indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"Помилка: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print(f"== getGifts(gift_name='{gift_name}', limit=3) ==")
    try:
        gifts = getGifts(gift_name=gift_name, limit=3, authData=auth)
        print(json.dumps(_summarize(gifts), indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"Помилка: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("== getAuctions(limit=5) ==")
    try:
        auctions = getAuctions(limit=5, authData=auth)
        print(json.dumps(_summarize(auctions), indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"Помилка: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
