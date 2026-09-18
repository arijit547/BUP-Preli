import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0)

test_notes = [
    ("SINGLE-NOTE-MULTI-005", ["The football event is postponed, solar output is reduced by 30 percent at hour 10, and keep grid usage below 50 kWh."]),
    ("BANGLA-OVERALL-008", ["সোলার আউটপুট ৮০ শতাংশ কমবে না, বরং ৮০ শতাংশে নেমে আসবে।"]),
    ("LANG-MIX-026", ["Battery discharge korba na 7 PM theke 9 PM, and grid usage limit 100 kWh."]),
    ("LANG-MIX-035", ["Cloud er jonno solar kombe 30%, ar evening e battery reserve 120 kWh maintain korte hobe."]),
]

dummy_hours = [{"hour": i, "demand_kwh": 20, "solar_kwh": 5, "tariff_bdt_per_kwh": 5} for i in range(24)]
dummy_battery = {
    "capacity_kwh": 200,
    "initial_energy_kwh": 50,
    "minimum_energy_kwh": 20,
    "max_charge_kwh_per_hour": 30,
    "max_discharge_kwh_per_hour": 30
}

for name, notes in test_notes:
    print("=" * 60)
    print(f"Testing {name}: {notes}")
    payload = {
        "scenario_id": name,
        "hours": dummy_hours,
        "battery": dummy_battery,
        "operator_notes": notes
    }
    try:
        res = client.post("/optimize-energy", json=payload)
        print("Status:", res.status_code)
        if res.status_code == 200:
            dirs = res.json().get("directive_interpretation")
            print("Directives:", json.dumps(dirs, indent=2))
        else:
            print("Error:", res.text)
    except Exception as e:
        print("Exception:", e)
