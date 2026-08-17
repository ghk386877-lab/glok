"""
Перевіряє сигнатуру update_auth() в aportalsmp через інтроспекцію - функція,
яка має вміти сама оновлювати authData через Pyrogram-логін, без ручного
копіювання з браузера.

Використання:
    python inspect_update_auth.py
"""
import inspect

import aportalsmp

print("=" * 60)
if hasattr(aportalsmp, "update_auth"):
    fn = aportalsmp.update_auth
    print(f"Сигнатура: update_auth{inspect.signature(fn)}")
    print(f"\nDocstring:\n{fn.__doc__}")
else:
    print("update_auth відсутня в цій версії aportalsmp.")
    print("Доступні функції з 'auth' у назві:")
    for name in dir(aportalsmp):
        if "auth" in name.lower():
            print(f"  {name}")
