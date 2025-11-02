from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN


SENSORS = (
("Svitlo GPV", "gpv"),
("Svitlo Next Status", ("next", "status")),
("Svitlo Next Start", ("next", "start")),
("Svitlo Next End", ("next", "end")),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
entities = [SvitloValueSensor(coord, name, path) for name, path in SENSORS]
entities.append(SvitloTodaySensor(coord))
async_add_entities(entities)


class SvitloBase(CoordinatorEntity):
_attr_has_entity_name = True
def __init__(self, coordinator, name: str):
super().__init__(coordinator)
self._attr_name = name


@property
def extra_state_attributes(self):
d = self.coordinator.data or {}
return {
"updated_at": d.get("updated_at"),
"address": d.get("address")
}


class SvitloValueSensor(SvitloBase, SensorEntity):
def __init__(self, coordinator, name: str, path):
super().__init__(coordinator, name)
self._path = path


@property
def native_value(self):
d = self.coordinator.data or {}
cur = d
if isinstance(self._path, tuple):
for k in self._path:
cur = (cur or {}).get(k)
return cur
return d.get(self._path)


class SvitloTodaySensor(SvitloBase, SensorEntity):
def __init__(self, coordinator):
super().__init__(coordinator, "Svitlo Intervals Today")


@property
def native_value(self):
# return count of intervals for convenience
d = self.coordinator.data or {}
arr = d.get("today") or []
return len(arr)


@property
def extra_state_attributes(self):
base = super().extra_state_attributes
d = self.coordinator.data or {}
base.update({"intervals": d.get("today")})
return base
