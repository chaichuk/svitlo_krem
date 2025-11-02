"""Config flow for Svitlo UA Power Outages integration."""
from typing import Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, REGIONS, REGION_PROVIDERS

class SvitloUAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Svitlo UA integration."""
    VERSION = 1

    def __init__(self):
        self._selected_region: Optional[str] = None

    async def async_step_user(self, user_input=None):
        """Step 1: Select region."""
        errors = {}
        if user_input is not None:
            self._selected_region = user_input["region"]
            # Якщо для регіону потрібен вибір постачальника – переходимо на наступний крок
            if REGION_PROVIDERS.get(self._selected_region):
                return await self.async_step_provider()
            else:
                # Якщо постачальника вибирати не потрібно, переходимо до вводу черги
                return await self.async_step_group()
        # Формуємо форму вибору регіону
        regions_list = list(REGIONS)  # Список названь регіонів
        schema = vol.Schema({
            vol.Required("region"): vol.In(regions_list)
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_provider(self, user_input=None):
        """Step 2: Select provider if required for region."""
        errors = {}
        if user_input is not None:
            # Зберігаємо вибраного постачальника і переходимо до вводу черги
            self._selected_provider = user_input["provider"]
            return await self.async_step_group()
        # Отримуємо список постачальників для вибраного регіону
        providers = REGION_PROVIDERS.get(self._selected_region, [])
        schema = vol.Schema({
            vol.Required("provider"): vol.In(providers)
        })
        return self.async_show_form(step_id="provider", data_schema=schema, errors=errors)

    async def async_step_group(self, user_input=None):
        """Step 3: Enter or select outage group number."""
        errors = {}
        if user_input is not None:
            group_str = user_input["group"]
            # Валідація формату групи (має бути напр. "1", "2.1", "6.2" тощо)
            if not self._validate_group_format(group_str):
                errors["base"] = "invalid_group"
            else:
                # Створюємо запис конфігурації з обраними параметрами
                return self.async_create_entry(title=f"{self._selected_region} - {group_str}", data={
                    "region": self._selected_region,
                    "provider": getattr(self, "_selected_provider", None),
                    "group": group_str
                })
        # Визначаємо приклад значення для підказки
        example = "1 або 2.1 або 6.2"
        schema = vol.Schema({
            vol.Required("group"): str  # користувач може ввести номер черги (рядок)
        })
        return self.async_show_form(step_id="group", data_schema=schema, errors=errors, description_placeholders={"example": example})

    @staticmethod
    def _validate_group_format(group: str) -> bool:
        """Перевірка, що група має формат числа або числа.числа."""
        if not group:
            return False
        # Дозволені формати: "X", "X.Y" де X,Y - цифри
        # Наприклад: "1", "2", "2.1", "10.2" тощо.
        parts = group.split(".")
        if len(parts) == 1:
            return parts[0].isdigit()
        elif len(parts) == 2:
            return parts[0].isdigit() and parts[1].isdigit()
        else:
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Дозволяє редагувати налаштування інтеграції (за потреби)."""
        return SvitloUAOptionsFlow(config_entry)

class SvitloUAOptionsFlow(config_entries.OptionsFlow):
    """Опціональний flow для редагування конфігурації (необов'язково)."""
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Початковий крок опційного flow - дозволяємо змінити лише групу, наприклад."""
        if user_input is not None:
            # Оновлюємо лише номер групи
            return self.async_create_entry(title="", data={"group": user_input["group"]})
        schema = vol.Schema({
            vol.Optional("group", default=self.config_entry.data.get("group", "")): str
        })
        return self.async_show_form(step_id="init", data_schema=schema)
