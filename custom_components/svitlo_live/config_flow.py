from __future__ import annotations
from typing import Any, Dict, List
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
)

# --- Регіони (укр), відсортовані ---
REGION_SLUG_TO_UI: Dict[str, str] = dict(sorted(REGIONS.items(), key=lambda kv: kv[1]))
REGION_UI_TO_SLUG: Dict[str, str] = {v: k for k, v in REGION_SLUG_TO_UI.items()}
REGION_UI_LIST: List[str] = list(REGION_SLUG_TO_UI.values())
REGION_UI_OPTIONS = [{"label": name, "value": name} for name in REGION_UI_LIST]

# --- Черги 1.1 … 6.2 ---
QUEUE_LIST: List[str] = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 3)]
QUEUE_OPTIONS = [{"label": q, "value": q} for q in QUEUE_LIST]
DEFAULT_QUEUE = "1.1"

# --- Інтервали: використовуємо ЛЕЙБЛИ як value у селекторі ---
INTERVAL_LABELS: List[str] = list(INTERVAL_LABEL_TO_SECONDS.keys())
INTERVAL_OPTIONS = [{"label": lbl, "value": lbl} for lbl in INTERVAL_LABELS]
DEFAULT_INTERVAL_LABEL = "15 хв"

# Реверсне відображення для OptionsFlow (секунди -> лейбл)
SECONDS_TO_LABEL = {v: k for k, v in INTERVAL_LABEL_TO_SECONDS.items()}


class SvitloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            region_ui = user_input[CONF_REGION]
            region_slug = REGION_UI_TO_SLUG.get(region_ui, region_ui)
            queue = user_input[CONF_QUEUE]

            # з лейбла отримуємо секунди
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

        default_region = REGION_UI_LIST[0] if REGION_UI_LIST else "Київська область"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REGION, default=default_region): selector({
                    "select": {"options": REGION_UI_OPTIONS, "mode": "dropdown"}
                }),
                vol.Required(CONF_QUEUE, default=DEFAULT_QUEUE): selector({
                    "select": {"options": QUEUE_OPTIONS, "mode": "dropdown"}
                }),
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL_LABEL): selector({
                    "select": {"options": INTERVAL_OPTIONS, "mode": "dropdown"}
                }),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    @callback
    def async_get_options_flow(self, config_entry):
        return SvitloOptionsFlow(config_entry)


class SvitloOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            region_ui = user_input[CONF_REGION]
            region_slug = REGION_UI_TO_SLUG.get(region_ui, region_ui)
            queue = user_input[CONF_QUEUE]

            interval_label = user_input[CONF_SCAN_INTERVAL]
            scan_seconds = int(INTERVAL_LABEL_TO_SECONDS.get(interval_label, 900))

            return self.async_create_entry(
                title="",
                data={CONF_REGION: region_slug, CONF_QUEUE: queue},
                options={CONF_SCAN_INTERVAL: scan_seconds},
            )

        saved_slug = self.entry.data.get(CONF_REGION)
        current_region_ui = REGION_SLUG_TO_UI.get(saved_slug, REGION_UI_LIST[0])
        current_queue = self.entry.data.get(CONF_QUEUE, DEFAULT_QUEUE)

        # маємо секунди в options → конвертуємо у лейбл для дропдауну
        current_seconds = int(self.entry.options.get(CONF_SCAN_INTERVAL, 900))
        current_interval_label = SECONDS_TO_LABEL.get(current_seconds, DEFAULT_INTERVAL_LABEL)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REGION, default=current_region_ui): selector({
                    "select": {"options": REGION_UI_OPTIONS, "mode": "dropdown"}
                }),
                vol.Required(CONF_QUEUE, default=current_queue): selector({
                    "select": {"options": QUEUE_OPTIONS, "mode": "dropdown"}
                }),
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval_label): selector({
                    "select": {"options": INTERVAL_OPTIONS, "mode": "dropdown"}
                }),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
