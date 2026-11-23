import pytest


@pytest.fixture
def offer() -> dict:
    """One Vast offer. SIMULATED: field names and types from a real 2026-11-23 response, values invented."""
    return {
        "id": 101, "machine_id": 7, "host_id": 9, "gpu_name": "RTX 4090", "num_gpus": 2, "gpu_frac": 0.25,
        "gpu_ram": 24564, "geolocation": "Guangdong, CN", "verification": "verified", "reliability": 0.99,
        "cpu_name": "AMD EPYC 7502", "cpu_cores_effective": 16.0, "cpu_ram": 128000, "disk_space": 500.0,
        "inet_up": 900.0, "inet_down": 950.0, "direct_port_count": 100, "dph_base": 0.8, "dph_total": 0.81,
        "min_bid": 0.5, "rentable": True, "duration": 864000.0, "gpu_max_power": 450.0,
        "public_ipaddr": "203.0.113.7", "hostname": "host.example", "webpage": None, "geolocode": 123,
    }
