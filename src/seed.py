"""Sample notes for the demo scenario: an offline field-maintenance assistant."""
import db
import memory

NOTES = [
    "Pump 3 is making a grinding noise at startup",
    "Replaced worn bearing on pump 3; grinding stopped after replacement",
    "Conveyor belt B keeps slipping under heavy load",
    "Tightened the tension roller on conveyor B, slipping fixed",
    "Hydraulic press is leaking oil near the left seal",
    "Swapped the O-ring seal on the hydraulic press, no more oil drips",
    "Compressor overheating after two hours of continuous run",
    "Cleaned the compressor air filter; temperature back to normal",
    "Cooling fan in electrical cabinet 7 is not spinning",
    "Replaced the fan motor in electrical cabinet 7",
    "Boiler pressure gauge reads zero although the boiler is running",
    "Calibrated the boiler pressure sensor, reading now matches the manual gauge",
    "Forklift battery drains within three hours",
    "Forklift battery cells were sulfated; replaced the battery pack",
    "Vibration on the CNC spindle is above the safe limit",
    "Rebalanced the CNC spindle, vibration back within limits",
    "Lubrication schedule for all gearboxes is every 500 operating hours",
    "Use ISO VG 220 gear oil for the main reducer",
    "Safety: lock out and tag out the panel before opening cabinet doors",
    "Emergency stop button on line 2 was sticking, replaced the switch",
    "Wi-Fi password for the maintenance room is maint-2026-xyz",
    "Gate code for warehouse B is 4471",
    "Air dryer drain valve clogged, causing water in the pneumatic lines",
    "Ordered spare bearings and O-rings, arriving next Tuesday",
    "Thermal camera shows a hot spot on the motor terminal of pump 5",
    "Tightened the loose terminal connection on the pump 5 motor",
    "Paint booth exhaust fan is making a rattling sound",
    "The rattling was a loose guard panel, secured with new bolts",
]


def load() -> int:
    existing = {m["text"] for m in db.all_memories()}
    n = 0
    for t in NOTES:
        if t not in existing:
            memory.add(t)
            n += 1
    return n


if __name__ == "__main__":
    db.init()
    print(f"Added {load()} sample notes")
