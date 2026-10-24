# Tenant commerce and creator marketplace

The existing tenant system provides separate accounts, roles, workspace collaboration,
invitations, storage quotas, credits, suspension, session revocation and audit logs.
New navigation adds **Billing & credits** and **Creator marketplace** for tenants,
and **Commerce & gateways** and **Marketplace** moderation for super administrators.

## Deploy

Run the documented `ansible/pull-and-deploy.yml` entry point. The normal deployment
now installs `commerce.py`; database initialization adds tables without replacing
existing data. Existing backup/restore behavior applies. Public HTTPS/DNS is required.

On the server create `/etc/africancreativity/payments.env`, root-owned with mode 0600:

```dotenv
COMMERCE_PUBLIC_URL=https://africancreativity.io
STRIPE_SECRET_KEY=replace-with-your-server-secret
PAYSTACK_SECRET_KEY=replace-with-your-server-secret
FLUTTERWAVE_SECRET_KEY=replace-with-your-server-secret
```

Only configure providers you use. Never commit this file or put keys into the
browser. Restart `africancreativity` after editing. Test and live keys use their
respective provider environments; configure and test sandbox payments first.
The gateway status means keys and public URL are configured, not that provider
credentials, merchant approval, currency access or live charges were tested.

## Billing

Super administrators publish one-time credit packages with title, currency, price
in integer minor units and credit quantity. Disable old packages to replace pricing;
orders retain their original amount, currency and credits. Supported two-decimal
currencies: USD, NGN, GBP, EUR, GHS, KES, ZAR; provider/account support varies.

Tenant administrators select a package and gateway and enter card/bank details on
the provider's site. Returning users open Billing and click **Verify payment**.
Server verification checks paid status, order reference, exact amount and currency.
An atomic state transition credits the tenant once, even on repeated verification.
Orders and ledgers are tenant scoped; platform administrators have the global view.
Paid orders provide a downloadable payment receipt record, not a tax invoice.

Verification is initiated by a signed-in tenant administrator. Webhooks, unattended
reconciliation, recurring subscriptions, refunds/chargebacks, tax calculation,
provider fee reconciliation and cash seller payouts are not implemented. Do not
advertise these as available. Provider API calls time out after 20 seconds; if a
checkout fails, retain the reference and check the provider before attempting another
charge. An order that lacks a provider reference needs operator reconciliation.

## Marketplace

Tenant administrators submit original text as lyrics, prompts or guides, confirm
rights, and set a whole-credit price. Submissions remain hidden from other tenants
until a super administrator approves them. Moderators can inspect content, approve,
reject or return to pending. Sellers can withdraw listings. Withdrawals do not revoke
purchased content. Public browsing does not expose the paid content; buyers receive
workspace access only after an atomic credit transfer. Duplicate purchases within a
tenant return the existing purchase without charging again. Suspended sellers are
excluded from new purchases. Sellers receive 90% rounded down in nonwithdrawable
platform credits; the platform retains the balance. License wording is displayed
in the marketplace and terms page. Operator identity and commercial/dispute terms
still require completion on the existing draft terms page.

This is a text-content marketplace, not audio/video distribution, cash escrow,
royalty accounting, or automated copyright clearance. Uploaded media stays private
under the existing project authorization checks.

## Validation

`python3 -m unittest discover -s tests -q`

`cd tests/browser && npm ci && npm test`

`ansible-playbook -i localhost, -c local ansible/pull-and-deploy.yml --syntax-check`

Automated tests mock payment providers; no real money is charged during tests.
