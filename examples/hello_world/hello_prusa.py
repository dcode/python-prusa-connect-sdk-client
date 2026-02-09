"""Hello Prusa example."""

from prusa.connect.client import PrusaConnectClient

# Credentials are automatically loaded from your environment or default local file
client = PrusaConnectClient()

print("My Printers:")
for printer in client.get_printers():
    status = printer.printer_state or "UNKNOWN"
    print(f"- {printer.name} ({status})")

    if printer.telemetry:
        print(f"  Temp: {printer.telemetry.temp_nozzle}°C")
