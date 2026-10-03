"""AI Ops official website + membership backend.

This service is the *business* side of AI Ops, deliberately separate from the
main control service (`hewenze11/ai-ops`):

  * it sells two things — course videos and a monthly Skills subscription;
  * it stores user accounts and what they own;
  * for subscribers it mints a Skills *pull key*, which the user's own control
    service presents to fetch their Skills from the hub.

It is a preview. Payments are SIMULATED behind a `PaymentProvider` interface so
the whole purchase -> unlock loop runs end to end; swapping in a real gateway
(WeChat Pay / Alipay / Stripe) means implementing one class, nothing else.

Security stance mirrors the control service: no secrets in source, no implicit
privilege, the admin surface is a separate token, and the Skills pull key is
checked on every request.
"""
