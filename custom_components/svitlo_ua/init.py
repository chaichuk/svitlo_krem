"""Це кастомна інтеграція 'Світло'."""
import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import SvitloDataUpdateCoordinator
from . import const

_LOGGER = logging.getLogger(__name__)

# Глобальний словник для збереження даних координатора
DOMAIN = const.DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Не використовується, оскільки використовується config_flow."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Налаштування та запуск інтеграції з config_entry."""
    hass.data.setdefault(DOMAIN, {})
    # Створюємо координатор даних
    coordinator = SvitloDataUpdateCoordinator(hass, entry.data["region"], entry.data.get("provider"), entry.data["group"])
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    # Додаємо платформи sensor, binary_sensor, calendar
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "calendar"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Виключення інтеграції повністю."""
    # Зупинка оновлень координатора
    coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.async_stop()
    # Виключити завантажені платформи
    return await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor", "calendar"])
