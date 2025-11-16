from __future__ import annotations
from typing import Any, Dict, List, Tuple
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import DOMAIN, CONF_REGION, CONF_QUEUE, REGIONS, REGION_QUEUE_MODE

REGION_SLUG_TO_UI: Dict[str, str] = dict(sorted(REGIONS.items(), key=lambda kv: kv[1]))
REGION_UI_TO_SLUG: Dict[str, str] = {v: k for k, v in REGION_SLUG_TO_UI.items()}
REGION_UI_LIST: List[str] = list(REGION_SLUG_TO_UI.values())
REGION_UI_OPTIONS = [{"label": name, "value": name} for name in REGION_UI_LIST]

def _queue_options_for_region(region_slug: str) -> Tuple[List[str], List[Dict[str, str]], str]:
    if region_slug == "vinnitska-oblast":
        values = [f"{i}.{j}" for i in range(1, 7) for j in (1, 2)]
        default = "1.1"
        options = [{"label": v, "value": v} for v in values]
        return values, options, default

    mode = REGION_QUEUE_MODE.get(region_slug, "DEFAULT")
    if mode == "CHERGA_NUM":
        values = [str(i) for i in range(1, 7)]
        default = "1"
    elif mode == "GRUPA_NUM":
        max_n = 12 if region_slug == "chernivetska-oblast" else 6
        values = [str(i) for i in range(1, max_n + 1)]
        default = "1"
    else:
        values = [f"{i}.{j}" for i in range(1, 7) for j in (1, 2)]
        default = "1.1"
    options = [{"label": v, "value": v} for v in values]
    return values, options, default

class SvitloConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._region_ui: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._region_ui = user_input[CONF_REGION]
            return await self.async_step_details()

        default_region = REGION_UI_LIST[0] if REGION_UI_LIST else "Київська область"
        data_schema = vol.Schema({
            vol.Required(CONF_REGION, default=default_region): selector({
                "select": {"options": REGION_UI_OPTIONS, "mode": "dropdown"}
            })
        })
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_details(self, user_input: dict[str, Any] | None = None):
        if not self._region_ui:
            return await self.async_step_user(user_input=None)

        region_ui = self._region_ui
        region_slug = REGION_UI_TO_SLUG.get(region_ui, region_ui)
        _, queue_options, default_queue = _queue_options_for_region(region_slug)

        if user_input is not None:
            queue = user_input[CONF_QUEUE]
            title = f"{region_ui} / {queue}"
            await self.async_set_unique_id(f"{region_slug}_{queue}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=title,
                data={CONF_REGION: region_slug, CONF_QUEUE: queue},
                options={},
            )

        data_schema = vol.Schema({
            vol.Required(CONF_QUEUE, default=default_queue): selector({
                "select": {"options": queue_options, "mode": "dropdown"}
            })
        })
        return self.async_show_form(
            step_id="details",
            data_schema=data_schema,
            description_placeholders={"region": region_ui},  # ← додано
        )

    @callback
    def async_get_options_flow(self, config_entry):
        return SvitloOptionsFlow(config_entry)

class SvitloOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self.entry = entry
        self._region_ui: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        saved_slug = self.entry.data.get(CONF_REGION)
        current_region_ui = REGION_SLUG_TO_UI.get(saved_slug, REGION_UI_LIST[0])

        if user_input is not None:
            self._region_ui = user_input[CONF_REGION]
            return await self.async_step_details()

        data_schema = vol.Schema({
            vol.Required(CONF_REGION, default=current_region_ui): selector({
                "select": {"options": REGION_UI_OPTIONS, "mode": "dropdown"}
            })
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_details(self, user_input: dict[str, Any] | None = None):
        if not self._region_ui:
            return await self.async_step_init(user_input=None)

        region_ui = self._region_ui
        region_slug = REGION_UI_TO_SLUG.get(region_ui, region_ui)

        saved_queue = self.entry.data.get(CONF_QUEUE)
        q_values, q_options, q_default = _queue_options_for_region(region_slug)
        default_queue = saved_queue if saved_queue in q_values else q_default

        if user_input is not None:
            queue = user_input[CONF_QUEUE]
            new_data = {**self.entry.data, CONF_REGION: region_slug, CONF_QUEUE: queue}
            return self.async_create_entry(title="", data=new_data, options=self.entry.options)

        data_schema = vol.Schema({
            vol.Required(CONF_QUEUE, default=default_queue): selector({
                "select": {"options": q_options, "mode": "dropdown"}
            })
        })
        return self.async_show_form(
            step_id="details",
            data_schema=data_schema,
            description_placeholders={"region": region_ui},  # ← додано
        )
