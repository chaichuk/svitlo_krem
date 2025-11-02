"""Sensors for Svitlo UA integration."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_TIMESTAMP

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor entities for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    entities.append(NextOutageStartSensor(coordinator))
    entities.append(NextPowerOnSensor(coordinator))
    entities.append(TimeToNextOutageSensor(coordinator))
    async_add_entities(entities)

class SvitloUASensorBase(SensorEntity):
    """Base class for Svitlo UA sensors."""
    _attr_has_entity_name = True  # використовувати friendly_name з device класу

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.region}_{coordinator.group}")},
            "name": f"Svitlo UA Power Outages ({coordinator.region})",
            "manufacturer": "Svitlo UA",
            "model": f"Outage Schedule {coordinator.region}"
        }
        # device_info дозволяє згрупувати сенсори і календар в один пристрій

    @property
    def available(self) -> bool:
        # Якщо coordinator.data є і не порожній – дані доступні
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_update(self):
        # Не викликаємо вручну update, Coordinator сам оновлює
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        # При додаванні сенсора – підписуємось на оновлення координатора
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        # При видаленні – відписуємось
        self.coordinator.async_remove_listener(self.async_write_ha_state)

class NextOutageStartSensor(SvitloUASensorBase):
    """Sensor for the datetime of the next outage start."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Next outage start"
        self._attr_unique_id = f"{coordinator.region}_{coordinator.group}_next_outage_start"
        self._attr_device_class = DEVICE_CLASS_TIMESTAMP

    @property
    def native_value(self):
        # Дата/час початку наступного відключення (або None якщо не заплановано)
        return self.coordinator.data.get("next_outage_start") if self.coordinator.data else None

class NextPowerOnSensor(SvitloUASensorBase):
    """Sensor for the datetime when power will be back on (next power on time)."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Next power on"
        self._attr_unique_id = f"{coordinator.region}_{coordinator.group}_next_power_on"
        self._attr_device_class = DEVICE_CLASS_TIMESTAMP

    @property
    def native_value(self):
        # Дата/час відновлення електропостачання (для найближчого відключення або поточного)
        return self.coordinator.data.get("next_power_on") if self.coordinator.data else None

class TimeToNextOutageSensor(SvitloUASensorBase):
    """Sensor for minutes remaining to the next outage."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Time to next outage"
        self._attr_unique_id = f"{coordinator.region}_{coordinator.group}_time_to_next_outage"
        self._attr_unit_of_measurement = "min"

    @property
    def native_value(self):
        # Кількість хвилин до наступного відключення (або None якщо не заплановано)
        return self.coordinator.data.get("time_to_next_outage") if self.coordinator.data else None
