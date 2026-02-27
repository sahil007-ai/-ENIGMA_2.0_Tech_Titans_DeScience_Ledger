# This file defines the hardcoded list of trusted research nodes active in the network.
# In a fully decentralized production system, this data might come from a
# Decentralized Autonomous Organization (DAO) registry contract on-chain.

VERIFIED_NODES = [
    {
        "id": "A-101",
        "type": "eDNA Sensor",
        "location": "Amazon Rainforest (Manaus)",
        "status": "Verified",
    },
    {
        "id": "S-205",
        "type": "Satellite Telemetry",
        "location": "Low Earth Orbit (Polar)",
        "status": "Syncing",
    },
    {
        "id": "A-103",
        "type": "eDNA Sensor",
        "location": "Congo Basin",
        "status": "Verified",
    },
    {
        "id": "OB-77",
        "type": "Ocean Buoy Array",
        "location": "Pacific Gyre",
        "status": "Verified",
    },
    {
        "id": "GS-99",
        "type": "Geospatial Seismic",
        "location": "Reykjavik, Iceland",
        "status": "Offline",
    },
]


def get_registered_nodes():
    """Returns the list of verified nodes."""
    return VERIFIED_NODES


def get_total_nodes_count():
    """Returns the total count of registered nodes."""
    return len(VERIFIED_NODES)
