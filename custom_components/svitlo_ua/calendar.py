"""Calendar entity for Svitlo UA integration (planned outages schedule)."""
from datetime import datetime, timedelta
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up calendar entity for outage schedule."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OutagesCalendar(coordinator)])

class OutagesCalendar(CalendarEntity):
    """Calendar entity representing today's and tomorrow's outage events."""
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Outages Schedule"
        self._attr_unique_id = f"{coordinator.region}_{coordinator.group}_outages_calendar"
        # Інформація про пристрій (та сама група пристроїв)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.region}_{coordinator.group}")},
            "name": f"Svitlo UA Power Outages ({coordinator.region})",
            "manufacturer": "Svitlo UA",
            "model": f"Outage Schedule {coordinator.region}"
        }

    @property
    def event(self) -> CalendarEvent:
        """Поточна або найближча подія (відключення)."""
        events = self._get_all_events()
        now = dt_util.now()
        # Знайти подію, яка зараз активна або наступна
        next_event = None
        for ev in events:
            if ev.start <= now < ev.end:
                # Якщо зараз триває відключення – це поточна подія
                next_event = ev
                break
            if ev.start >= now:
                next_event = ev
                break
        return next_event

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        """Повернути усі події в заданому інтервалі (для перегляду календаря)."""
        events = self._get_all_events()
        result = []
        for event in events:
            if event.end <= start_date or event.start >= end_date:
                continue  # подія поза запитуваним інтервалом
            result.append(event)
        return result

    def _get_all_events(self):
        """Отримати список CalendarEvent для усіх запланованих відключень (сьогодні і завтра)."""
        events = []
        data = self.coordinator.data
        if not data:
            return events
        # Об'єднати сьогоднішні і завтрашні події
        for day_key in ("events_today", "events_tomorrow"):
            for interval in data.get(day_key, []):
                if interval is None:
                    continue
                start_dt, end_dt = interval
                # Формуємо об'єкт CalendarEvent
                event = CalendarEvent(
                    start=start_dt,
                    end=end_dt,
                    summary="Planned outage",       # Короткий опис події
                    description="Scheduled power outage"  # Можна додати довший опис
                )
                events.append(event)
        # Сортуємо події за часом початку
        events.sort(key=lambda ev: ev.start)
        return events

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self):
        # Підписуємось на оновлення координатора, щоб календар оновлювався автоматично
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self.async_write_ha_state)
