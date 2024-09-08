from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.exceptions import ModbusException
from modbus_helpers import log_results

def start_modbus_scan(config, stop_event, result_text, progress_bar):
    client = ModbusClient(
        method='rtu',
        port=config['port'],
        baudrate=config['baudrate'],
        parity=config['parity'],
        stopbits=config['stopbits'],
        bytesize=config['bytesize'],
        timeout=config['timeout']
    )

    if not client.connect():
        result_text.insert("end", f"Failed to connect to {config['port']}\n")
        return

    total_addresses = config['end_address'] - config['start_address'] + 1
    progress_bar['maximum'] = total_addresses

    for i, address in enumerate(range(config['start_address'], config['end_address'] + 1)):
        if stop_event.is_set():  # Check if the stop signal was sent
            result_text.insert("end", "Scan stopped by the user.\n")
            break  # Exit the loop to stop the scan

        progress_bar['value'] = i + 1
        try:
            result = client.read_holding_registers(0, 1, unit=address)
            if result.isError():
                result_text.insert("end", f"No device at address {address}\n")
            else:
                result_text.insert("end", f"Device at address {address}: {result.registers}\n")
        except ModbusException as e:
            result_text.insert("end", f"Error at address {address}: {e}\n")

    log_results(result_text.get(1.0, "end"))
    client.close()
