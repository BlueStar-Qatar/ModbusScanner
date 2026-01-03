from __future__ import annotations

from time import monotonic
from typing import Any, Callable, Dict

from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.exceptions import ModbusException, ModbusIOException

Event = Dict[str, Any]
Emit = Callable[[Event], None]


def _probe(client: ModbusClient, config: Dict[str, Any], unit_id: int):
    method = config.get("probe_method", "holding_registers")
    register = int(config.get("probe_register", 0))
    count = int(config.get("probe_count", 1))

    if method == "input_registers":
        return client.read_input_registers(register, count, unit=unit_id)

    return client.read_holding_registers(register, count, unit=unit_id)


def start_modbus_scan(config: Dict[str, Any], stop_event, emit: Emit) -> None:
    """
    Worker-thread Modbus scan. This function must not touch Tkinter widgets.

    Emits events to the caller via `emit({...})`.
    """

    def safe_emit(event: Event) -> None:
        try:
            emit(event)
        except Exception:
            # If the UI has closed or the queue is unavailable, stop emitting.
            return

    port = config.get("port", "")
    safe_emit({"type": "log", "message": f"Connecting to {port}..."})

    client = ModbusClient(
        method="rtu",
        port=config["port"],
        baudrate=config["baudrate"],
        parity=config["parity"],
        stopbits=config["stopbits"],
        bytesize=config["bytesize"],
        timeout=config["timeout"],
    )

    responded = 0
    responded_exception = 0
    no_response = 0
    errors = 0
    stopped = False

    try:
        if stop_event.is_set():
            stopped = True
            safe_emit({"type": "done", "stopped": True})
            return

        if not client.connect():
            safe_emit({"type": "error", "message": f"Failed to connect to {port}"})
            safe_emit({"type": "done", "stopped": True})
            return

        safe_emit({"type": "client_ready", "client": client})

        start_address = int(config["start_address"])
        end_address = int(config["end_address"])
        total_addresses = end_address - start_address + 1
        safe_emit({"type": "progress_init", "total": total_addresses})

        for index, address in enumerate(range(start_address, end_address + 1), start=1):
            if stop_event.is_set():
                stopped = True
                safe_emit({"type": "log", "message": "Scan stop requested. Finishing current request..."})
                break

            safe_emit({"type": "progress", "current": index, "total": total_addresses, "address": address})

            t0 = monotonic()
            try:
                result = _probe(client, config, unit_id=address)
                elapsed_ms = int((monotonic() - t0) * 1000)

                if result is None:
                    no_response += 1
                    safe_emit(
                        {
                            "type": "result",
                            "address": address,
                            "status": "no_response",
                            "response_time_ms": elapsed_ms,
                            "details": "No response",
                        }
                    )
                    continue

                if isinstance(result, ModbusIOException):
                    no_response += 1
                    safe_emit(
                        {
                            "type": "result",
                            "address": address,
                            "status": "no_response",
                            "response_time_ms": elapsed_ms,
                            "details": str(result),
                        }
                    )
                    continue

                if hasattr(result, "isError") and result.isError():
                    # Exception response still implies a device responded at this unit id.
                    responded_exception += 1
                    safe_emit(
                        {
                            "type": "result",
                            "address": address,
                            "status": "exception",
                            "response_time_ms": elapsed_ms,
                            "details": str(result),
                        }
                    )
                    continue

                responded += 1
                registers = getattr(result, "registers", None)
                safe_emit(
                    {
                        "type": "result",
                        "address": address,
                        "status": "responded",
                        "response_time_ms": elapsed_ms,
                        "details": registers if registers is not None else str(result),
                    }
                )
            except ModbusException as exc:
                elapsed_ms = int((monotonic() - t0) * 1000)
                errors += 1
                safe_emit(
                    {
                        "type": "result",
                        "address": address,
                        "status": "error",
                        "response_time_ms": elapsed_ms,
                        "details": str(exc),
                    }
                )
            except Exception as exc:
                elapsed_ms = int((monotonic() - t0) * 1000)
                errors += 1
                safe_emit(
                    {
                        "type": "result",
                        "address": address,
                        "status": "error",
                        "response_time_ms": elapsed_ms,
                        "details": f"{type(exc).__name__}: {exc}",
                    }
                )

        safe_emit(
            {
                "type": "done",
                "stopped": stopped,
                "summary": {
                    "responded": responded,
                    "responded_exception": responded_exception,
                    "no_response": no_response,
                    "errors": errors,
                },
            }
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


def read_modbus_registers(config: Dict[str, Any], stop_event, emit: Emit) -> None:
    """
    Worker-thread Modbus read for a single slave/unit id. This function must not touch Tkinter widgets.

    Emits events to the caller via `emit({...})`.
    """

    def safe_emit(event: Event) -> None:
        try:
            emit(event)
        except Exception:
            return

    port = config.get("port", "")
    unit_id = int(config.get("unit_id", 0))
    address = int(config.get("read_address", 0))
    count = int(config.get("read_count", 0))
    read_type = config.get("read_type", "holding_registers")

    safe_emit({"type": "read_log", "message": f"Connecting to {port}..."})

    client = ModbusClient(
        method="rtu",
        port=config["port"],
        baudrate=config["baudrate"],
        parity=config["parity"],
        stopbits=config["stopbits"],
        bytesize=config["bytesize"],
        timeout=config["timeout"],
    )

    try:
        if stop_event.is_set():
            safe_emit({"type": "read_done", "stopped": True})
            return

        if not client.connect():
            safe_emit({"type": "read_error", "message": f"Failed to connect to {port}"})
            safe_emit({"type": "read_done", "stopped": True})
            return

        safe_emit({"type": "read_client_ready", "client": client})

        safe_emit(
            {
                "type": "read_log",
                "message": f"Reading {read_type} unit={unit_id} address={address} count={count}...",
            }
        )

        t0 = monotonic()
        try:
            if stop_event.is_set():
                safe_emit({"type": "read_done", "stopped": True})
                return

            if read_type == "input_registers":
                result = client.read_input_registers(address, count, unit=unit_id)
            elif read_type == "coils":
                result = client.read_coils(address, count, unit=unit_id)
            elif read_type == "discrete_inputs":
                result = client.read_discrete_inputs(address, count, unit=unit_id)
            else:
                result = client.read_holding_registers(address, count, unit=unit_id)
            elapsed_ms = int((monotonic() - t0) * 1000)

            if result is None or isinstance(result, ModbusIOException):
                safe_emit({"type": "read_error", "message": f"No response from slave {unit_id}."})
                safe_emit({"type": "read_done", "stopped": False})
                return

            if hasattr(result, "isError") and result.isError():
                safe_emit({"type": "read_error", "message": str(result)})
                safe_emit({"type": "read_done", "stopped": False})
                return

            registers = getattr(result, "registers", None)
            bits = getattr(result, "bits", None)
            if isinstance(bits, list):
                bits = bits[:count]
            else:
                bits = []
            safe_emit(
                {
                    "type": "read_result",
                    "unit_id": unit_id,
                    "read_type": read_type,
                    "address": address,
                    "count": count,
                    "response_time_ms": elapsed_ms,
                    "registers": registers if registers is not None else [],
                    "bits": bits,
                }
            )
            safe_emit({"type": "read_done", "stopped": False})
        except ModbusException as exc:
            safe_emit({"type": "read_error", "message": str(exc)})
            safe_emit({"type": "read_done", "stopped": False})
        except Exception as exc:
            safe_emit({"type": "read_error", "message": f"{type(exc).__name__}: {exc}"})
            safe_emit({"type": "read_done", "stopped": False})
    finally:
        try:
            client.close()
        except Exception:
            pass
