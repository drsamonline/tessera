"""Real provider connectors, behind the transport seam.

    from tessera.providers import HubSpotConnector, SalesforceConnector, ZendeskConnector
    from tessera.transport import HttpTransport

    node = HubSpotConnector("hubspot", HttpTransport(), tenant_id, token="...")

Each of these must pass `tessera.conformance.run_conformance()` before it ships.
That is the whole point of the suite: four connectors, one contract.
"""

from .base import DEFAULT_POLICY, ProviderConnector
from .hubspot import HubSpotConnector
from .salesforce import SalesforceConnector
from .zendesk import ZendeskConnector

__all__ = [
    "ProviderConnector", "DEFAULT_POLICY",
    "HubSpotConnector", "SalesforceConnector", "ZendeskConnector",
]
