from __future__ import annotations
from typing import Any, Dict, List, Tuple
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    CONF_REGION,
    CONF_QUEUE,
    CONF_SCAN_INTERVAL,
    REGIONS,
    INTERVAL_LABEL_TO_SECONDS,
    REGION_QUEUE_MODE,  # важливо
)

# --- Регіони (укр), відсортовані ---
REGION_SLUG_TO_UI: Dict[str, str] = dict(sorted(REGIONS.items(), key=lambda kv: kv[1]))
REGION_UI_TO_SLUG: Dict[str, str] = {v: k for k, v in REGION_SLUG_TO_UI.items()}
REGION_UI_LIST: List[str] = list(REGION_SLUG_TO_UI.values())
REGION_UI_OPTIONS = [{"label": name, "value": name} for name in REGION_UI_LIST]

# --- Інтервали: використовуємо ЛЕЙБЛИ як value у селекторі ---
INTERVAL_LABELS: List[str] = list(INTERVAL_LABEL_TO_SECONDS.keys())
INTERVAL_OPTIONS = [{"label": lbl, "value": lbl} for lbl in INTERVAL_LABELS]
DEFAULT_INTERVAL_LABEL = "15 хв"

# Реверсне відображення для OptionsFlow (секунди -> лейбл)
SECONDS_TO_LABEL = {v: k for k, v in INTERVAL_LABEL_TO_SECONDS.items()}


def _queue_options_for_region(region_slug: str) -> Tuple[List[str], List[Dict[str, str]], str]:
    """
    Повертає: (queue_values, selector_options, default_value)
    - DEFAULT (більшість областей): X.Y (1.1..6.2)
    - CHERGA_NUM (Вінницька): 1..6
    - GRUPA_NUM (Чернівецька/Донецька): 1..12 (Чернівецька) або 1..6 (Донецька)
    """
    mode = REGION_QUEUE_MODE.get(region_slug, "DEFAULT")

    if mode == "CHERGA_NUM":
        values = [str(i) for i in range(1, 7)]
        default = "1"
    elif mode == "GRUPA_NUM":
        # Чернівецька — 1..12, Донецька — 1..6
        max_n = 12 if region_slug == "chernivetska-oblast" else 6
        values = [str(i) for i in range(1, max_n + 1)]
        default = "1"
    else:
        # DEFAULT: підчерги X.Y
        values = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 2 + 1)]
        default = "1.1"

    options = [{"label": v, "value": v} for v in values]
    return values, options, default


class SvitloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._region_ui: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # КРОК 1: вибір області
        if user_input is not None:
            self._region_ui = user_input[CONF_REGION]
            return await self.async_step_details()

        default_region = REGION_UI_LIST[0] if REGION_UI_LIST else "Київська область"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REGION, default=default_region): selector({
                    "select": {"options": REGION_UI_OPTIONS, "mode": "dropdown"}
                }),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_details(self, user_input: dict[str, Any] | None = None):
        # КРОК 2: вибір черги/групи + інтервал
        if not self._region_ui:
            # якщо зайшли сюди напряму — вертаємо на перший крок
            return await self.async_step_user(user_input=None)

        region_ui = self._region_ui
        region_slug = REGION_UI_TO_SLUG.get(region_ui, region_ui)
        _, queue_options, default_queue = _queue_options_for_region(region_slug)

        if user_input is not None:
            queue = user_input[CONF_QUEUE]
            interval_label = user_input[CONF_SCAN_INTERVAL]
            scan_seconds = int(INTERVAL_LABEL_TO_SECONDS.get(interval_label, 900))

            title = f"{region_ui} / {queue}"
            await self.async_set_unique_id(f"{region_slug}_{queue}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=title,
                data={CONF_REGION: region_slug, CONF_QUEUE: queue},
                options={CONF_SCAN_INTERVAL: scan_seconds},
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_QUEUE, default=default_queue): selector({
                    "select": {"options": queue_options, "mode": "dropdown"}
                }),
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL_LABEL): selector({
                    "select": {"options": INTERVAL_OPTIONS, "mode": "dropdown"}
                }),
            }
        )
        return self.async_show_form(step_id="details", data_schema=data_schema)

    @callback
    def async_get_options_flow(self, config_entry):
        return SvitloOptionsFlow(config_entry)


class SvitloOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        self._region_ui: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        # КРОК 1 (options): вибір області
        saved_slug = self.entry.data.get(CONF_REGION)
        current_region_ui = REGION_SLUG_TO_UI.get(saved_slug, REGION_UI_LIST[0])

        if user_input is not None:
            self._region_ui = user_input[CONF_REGION]
            return await self.async_step_details()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REGION, default=current_region_ui): selector({
                    "select": {"options": REGION_UI_OPTIONS, "mode": "dropdown"}
                }),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_details(self, user_input: dict[str, Any] | None = None):
        # КРОК 2 (options): вибір черги/групи для вибраної області + інтервал
        if not self._region_ui:
            # якщо зайшли сюди напряму — повернемось на перший крок
            return await self.async_step_init(user_input=None)

        region_ui = self._region_ui
        region_slug = REGION_UI_TO_SLUG.get(region_ui, region_ui)

        # поточні значення для підстановки
        saved_queue = self.entry.data.get(CONF_QUEUE)
        current_seconds = int(self.entry.options.get(CONF_SCAN_INTERVAL, 900))
        current_interval_label = SECONDS_TO_LABEL.get(current_seconds, DEFAULT_INTERVAL_LABEL)

        # новий список черг/груп залежно від області
        q_values, q_options, q_default = _queue_options_for_region(region_slug)
        # якщо збережений queue підходить — проставимо його як дефолт, інакше дефолтний
        default_queue = saved_queue if saved_queue in q_values else q_default

        if user_input is not None:
            queue = user_input[CONF_QUEUE]
            interval_label = user_input[CONF_SCAN_INTERVAL]
            scan_seconds = int(INTERVAL_LABEL_TO_SECONDS.get(interval_label, 900))

            # Оновлюємо і data, і options (region може змінюватись в options!)
            new_data = {**self.entry.data, CONF_REGION: region_slug, CONF_QUEUE: queue}
            new_options = {**self.entry.options, CONF_SCAN_INTERVAL: scan_seconds}

            return self.async_create_entry(title="", data=new_data, options=new_options)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_QUEUE, default=default_queue): selector({
                    "select": {"options": q_options, "mode": "dropdown"}
                }),
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval_label): selector({
                    "select": {"options": INTERVAL_OPTIONS, "mode": "dropdown"}
                }),
            }
        )
        return self.async_show_form(step_id="details", data_schema=data_schema)
