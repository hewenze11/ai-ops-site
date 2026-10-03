"""Payment provider boundary.

The website never talks to a gateway directly — it asks a `PaymentProvider` to
create a checkout and to confirm payment. In this preview the only provider is
`SimulatedProvider`, which "pays" immediately. Wiring a real gateway later means
adding a class here and selecting it via `AI_OPS_SITE_PAYMENT_PROVIDER`; no other
module needs to change.

A real provider would:
  * create_checkout -> call the gateway, return a redirect URL / QR payload;
  * confirm_payment -> verify an async callback signature before marking paid.
The interface keeps both steps so the swap is mechanical.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Checkout:
    order_id: str
    provider: str
    provider_ref: str
    # Where the browser should go to pay. For the simulator this is an internal
    # confirmation URL; a real gateway returns its own hosted page.
    redirect_url: str
    # True when the payment is already settled (simulator). Real gateways return
    # False and settle later via callback.
    settled: bool


class PaymentProvider(Protocol):
    name: str

    def create_checkout(self, order_id: str, amount_cents: int, description: str) -> Checkout: ...

    def confirm_payment(self, provider_ref: str) -> bool:
        """Return True iff the provider confirms the payment is settled."""
        ...


class SimulatedProvider:
    """Immediate, no-network payment used for local runs and tests.

    It is loud about being fake: every order records provider='simulated' so it
    can never be mistaken for a real sale.
    """

    name = "simulated"

    def create_checkout(self, order_id: str, amount_cents: int, description: str) -> Checkout:
        ref = "sim_" + uuid.uuid4().hex[:20]
        # A zero-price item is settled on the spot; anything else is too (this is
        # the simulator) but through the /checkout/{order}/confirm hop so the UI
        # exercises the same flow a real gateway would.
        settled = amount_cents <= 0
        return Checkout(order_id=order_id, provider=self.name, provider_ref=ref,
                        redirect_url=f"/api/v1/orders/{order_id}/simulate-pay",
                        settled=settled)

    def confirm_payment(self, provider_ref: str) -> bool:
        return True


def make_provider(name: str) -> PaymentProvider:
    providers = {"simulated": SimulatedProvider}
    if name not in providers:
        raise SystemExit(
            f"unknown payment provider {name!r}; available: {', '.join(providers)} "
            "(a real gateway must be implemented before it can be selected)")
    return providers[name]()
