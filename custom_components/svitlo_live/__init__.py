from __future__ import annotations
import logging
import shutil
from pathlib import Path
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_REGION,
    CONF_QUEUE,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import SvitloCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Svitlo Live component."""
    # Копіюємо blueprints при першому завантаженні компонента
    await hass.async_add_executor_job(_copy_blueprints, hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Svitlo.live v2 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Фіксований інтервал опитування (15 хв)
    config = {
        CONF_REGION: entry.data[CONF_REGION],
        CONF_QUEUE: entry.data[CONF_QUEUE],
        "scan_interval_seconds": DEFAULT_SCAN_INTERVAL,
    }
    
    coordinator = SvitloCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Svitlo.live v2 entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


def _copy_blueprints(hass: HomeAssistant) -> None:
    """Copy blueprints to the Home Assistant blueprints directory."""
    try:
        # Шлях до blueprints в інтеграції
        integration_path = Path(__file__).parent
        source_blueprints = integration_path / "blueprints" / "automation"
        
        if not source_blueprints.exists():
            _LOGGER.debug("No blueprints directory found in Svitlo Live integration")
            return
        
        # Шлях до blueprints в Home Assistant
        config_dir = Path(hass.config.path())
        target_blueprints = config_dir / "blueprints" / "automation" / "svitlo_live"
        
        # Створюємо папку якщо не існує
        target_blueprints.mkdir(parents=True, exist_ok=True)
        
        # Копіюємо всі blueprint файли
        copied_count = 0
        for blueprint_file in source_blueprints.glob("*.yaml"):
            target_file = target_blueprints / blueprint_file.name
            
            # Копіюємо тільки якщо файл не існує або відрізняється
            if not target_file.exists() or blueprint_file.stat().st_mtime > target_file.stat().st_mtime:
                shutil.copy2(blueprint_file, target_file)
                copied_count += 1
                _LOGGER.info(f"Copied Svitlo Live blueprint: {blueprint_file.name}")
        
        if copied_count > 0:
            _LOGGER.info(f"Successfully copied {copied_count} Svitlo Live blueprint(s)")
        else:
            _LOGGER.debug("All Svitlo Live blueprints are up to date")
            
    except Exception as e:
        _LOGGER.error(f"Failed to copy Svitlo Live blueprints: {e}")
