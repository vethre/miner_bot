from collections import deque, defaultdict
import time
from aiogram import BaseMiddleware, types


class AntiFlood(BaseMiddleware):
    """
    Простая реализация анти-флуда.
      • limit        – сколько событий подряд допускаем
      • window       – в каком окне (сек) эти события считаем
      • mute_seconds – на сколько секунд «глушим» юзера, если лимит превышен
    """

    def __init__(self, *, limit: int = 6, window: int = 10, mute_seconds: int = 90):
        self.limit = limit
        self.window = window
        self.mute = mute_seconds

        self._events: dict[int, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.limit)
        )
        self._muted_until: dict[int, float] = defaultdict(float)

    # ────────────────────────────────────────────────────────────────
    async def __call__(self, handler, event: types.TelegramObject, data):
        user_id = getattr(event.from_user, "id", None)
        if user_id is None:            # системные апдейты, чат-джоины и т.п.
            return await handler(event, data)

        now = time.time()

        # ── юзер в «тишине»? ─────────────────────────────────────────
        if now < self._muted_until[user_id]:
            try:
                await event.answer("⏳ Подожди немного – ты слишком активно спамишь.")
            except Exception:
                pass
            return  # глушим событие

        # ── регистрируем событие ────────────────────────────────────
        q = self._events[user_id]
        q.append(now)

        # если deque заполнена и весь интервал ≤ window → активируем мут
        if len(q) == self.limit and (q[-1] - q[0]) <= self.window:
            self._muted_until[user_id] = now + self.mute
            # однократное предупреждение
            try:
                await event.answer("⏳ Слишком много действий подряд. Сделай паузу…")
            except Exception:
                pass
            return  # не передаём в хендлер

        # всё ок – пропускаем событие дальше
        return await handler(event, data)
