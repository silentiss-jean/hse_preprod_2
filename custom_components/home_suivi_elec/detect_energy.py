# detect_energy.py
from homeassistant.helpers import entity_registry as er, device_registry as dr

entity_reg = er.async_get(hass)
device_reg = dr.async_get(hass)

ENERGY_INTEGRATIONS = ["powercalc", "hue", "tplink", "tapo", "tradfri", "sonoff"]

for state in hass.states.async_all("sensor"):
    entity_id = state.entity_id
    if not entity_id.startswith("sensor."):
        continue

    entry = entity_reg.async_get(entity_id)
    if entry and entry.device_id:
        device = device_reg.async_get(entry.device_id)
        integration = None
        if device and device.identifiers:
            integration = str(list(device.identifiers)[0][0]).lower()
        if integration in ENERGY_INTEGRATIONS:
            print (f"{entity_id} → integration fiable: {integration}")
