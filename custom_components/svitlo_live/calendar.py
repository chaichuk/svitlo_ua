from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.helpers import device_registry as dr  # ⬅️ додано

from .const import DOMAIN

# Таймзона України (не імпортуємо з coordinator, щоб уникнути циклу)
TZ_KYIV = dt_util.get_time_zone("Europe/Kyiv")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # ⬇️ передаємо entry, щоб за бажанням у майбутньому тягнути options — не завадить
    async_add_entities([SvitloCalendar(coordinator, entry)])


class SvitloCalendar(CoordinatorEntity, CalendarEntity):
    """Календар відключень світла для конкретного регіону/черги."""

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._region = getattr(coordinator, "region", "region")
        self._queue = getattr(coordinator, "queue", "queue")

        self._attr_unique_id = f"svitlo_calendar_{self._region}_{self._queue}"
        self._event: Optional[CalendarEvent] = None

    # Динамічне ім'я ентіті: підтягуємо назву пристрою, якщо користувач її змінив
    @property
    def name(self) -> str:
        return f"Світло • {self._device_label()}"

    # ---- обов'язково для стану календаря ----
    @property
    def event(self) -> Optional[CalendarEvent]:
        """Поточна або найближча подія (використовується для state)."""
        return self._event

    async def async_update(self) -> None:
        """Оновити self._event з координатора (поточна або найближча)."""
        now_utc = dt_util.utcnow()
        # беремо події за сьогодні+завтра із запасом
        start = now_utc - timedelta(days=1)
        end = now_utc + timedelta(days=2)
        events = await self.async_get_events(self.hass, start, end)

        # відсортуємо, знайдемо поточну або найближчу
        events.sort(key=lambda e: e.start)
        current = next((e for e in events if e.start <= now_utc < e.end), None)
        upcoming = next((e for e in events if e.start > now_utc), None)
        self._event = current or upcoming

    # ---- стандартні штуки ----
    @property
    def available(self) -> bool:
        return bool(self.coordinator.last_update_success)

    @property
    def device_info(self) -> dict[str, Any]:
        # ВАЖЛИВО: identifiers повинні збігатися з тим, що використовуєш для пошуку пристрою
        return {
            "identifiers": {(DOMAIN, f"{self._region}_{self._queue}")},
            "manufacturer": "svitlo.live",
            "model": f"Queue {self._queue}",
            "name": f"Світло • {self._region} / {self._queue}",
        }

    # ---- події з координатора ----
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> List[CalendarEvent]:
        """
        Повертаємо події 'Немає світла' у вказаному діапазоні.
        Події створюються на базі today_48half / tomorrow_48half з координатора.
        """
        d = getattr(self.coordinator, "data", {}) or {}
        today_half = d.get("today_48half") or []
        tomorrow_half = d.get("tomorrow_48half") or []
        date_today_str = d.get("date")
        date_tomorrow_str = d.get("tomorrow_date")

        events: List[CalendarEvent] = []
        events.extend(self._build_day_events(date_today_str, today_half))
        events.extend(self._build_day_events(date_tomorrow_str, tomorrow_half))

        # Фільтрація за діапазоном, який запросив HA
        filtered: List[CalendarEvent] = []
        for ev in events:
            ev_start = ev.start if ev.start.tzinfo else dt_util.as_utc(ev.start)
            ev_end = ev.end if ev.end.tzinfo else dt_util.as_utc(ev.end)
            if ev_start < end_date and ev_end > start_date:
                filtered.append(ev)

        return filtered

    def _build_day_events(self, date_str: str | None, halfhours: list[str]) -> List[CalendarEvent]:
        """Генеруємо події для одного дня (послідовності 'off' у 48 слотах)."""
        if not date_str or not halfhours or len(halfhours) != 48:
            return []

        base_day = datetime.fromisoformat(date_str).date()
        events: List[CalendarEvent] = []

        current_state = halfhours[0]
        start_idx = 0

        for i in range(1, 48):
            if halfhours[i] != current_state:
                if current_state == "off":
                    events.append(self._make_event(base_day, start_idx, i))
                current_state = halfhours[i]
                start_idx = i

        # Якщо день завершується у стані "off" — подія до півночі
        if current_state == "off":
            events.append(self._make_event(base_day, start_idx, 48))

        return events

    def _make_event(self, day, start_idx: int, end_idx: int) -> CalendarEvent:
        """Створює CalendarEvent для проміжку [start_idx; end_idx) у півгодинах."""
        start_h = start_idx // 2
        start_m = 30 if start_idx % 2 else 0
        end_h = end_idx // 2
        end_m = 30 if end_idx % 2 else 0

        start_local = datetime.combine(day, datetime.min.time()).replace(
            hour=start_h, minute=start_m, tzinfo=TZ_KYIV
        )
        if end_idx < 48:
            end_local = datetime.combine(day, datetime.min.time()).replace(
                hour=end_h, minute=end_m, tzinfo=TZ_KYIV
            )
        else:
            end_local = datetime.combine(day + timedelta(days=1), datetime.min.time()).replace(
                tzinfo=TZ_KYIV
            )

        start_utc = dt_util.as_utc(start_local)
        end_utc = dt_util.as_utc(end_local)

        prefix = f"[{self._device_label()}]"
        return CalendarEvent(
            summary=f"{prefix} ❌ Відключення електроенергії",
            start=start_utc,
            end=end_utc,
            description=f"{prefix} Немає світла {start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}",
        )

    # -------------------------
    # Допоміжне: назва з Device Registry або дефолт
    # -------------------------
    def _device_label(self) -> str:
        """Повертає ім'я пристрою з реєстру (name_by_user -> name) або дефолт."""
        try:
            dev_reg = dr.async_get(self.hass)
            device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{self._region}_{self._queue}")})
            if device:
                # name_by_user має пріоритет, якщо користувач перейменував
                if device.name_by_user:
                    return device.name_by_user
                if device.name:
                    return device.name
        except Exception:
            # не драматизуємо, просто впадемо на дефолт
            pass
        return f"{self._region} / {self._queue}"
