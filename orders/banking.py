"""
Single source of truth for the EFT banking details shown across all
invoicing -- manual invoices (manual_invoice.py) and order invoices/PDFs
(views.py), mirrored in the frontend's checkout and order-tracking pages
(pokemart-frontend/src/app/checkout/page.tsx and
pokemart-frontend/src/app/orders/[id]/page.tsx, which keep their own copy
since they're a separate app/deploy and can't import Python).

Michael, 2026-08-18: "I need to change my banking details for pokebulk, on
all invoicing" -- previously the same details were hardcoded separately in
orders/manual_invoice.py and orders/views.py, easy to update one and miss
the other. Update ONLY here on the backend going forward (and remember the
two frontend EFT_DETAILS consts still need updating by hand alongside it).
"""

EFT_BANKING_DETAILS = {
    "account_holder": "Poke Bulk SA (Pty) Ltd",
    "bank": "Capitec Business",
    "account_type": "Current Account",
    "account_number": "1055771166",
    "branch_code": "450105",
}

# Pre-built for the two HTML invoice builders -- same &nbsp;|&nbsp;
# separator style both already used.
EFT_BANKING_DETAILS_HTML = (
    f'{EFT_BANKING_DETAILS["account_holder"]} &nbsp;|&nbsp; '
    f'{EFT_BANKING_DETAILS["bank"]} {EFT_BANKING_DETAILS["account_type"]} &nbsp;|&nbsp; '
    f'Branch: {EFT_BANKING_DETAILS["branch_code"]} &nbsp;|&nbsp; '
    f'Acc: {EFT_BANKING_DETAILS["account_number"]}'
)
