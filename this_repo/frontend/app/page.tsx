import Dashboard from "../components/Dashboard";

const mockBom = `SmartPatch X1
- Nordic nRF52840 BLE, 2402 MHz, 0 dBm
- Realtek RTL8723DE WiFi+BT, 2412 MHz, 20 dBm
- wearable, body_worn: true
- target regions: US, EU, CA`;

export default function Page() {
  return <Dashboard initialBom={mockBom} />;
}
