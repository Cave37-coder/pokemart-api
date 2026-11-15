# Graph Report - pokemart-api  (2026-08-17)

## Corpus Check
- 359 files · ~216,693 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1601 nodes · 2479 edges · 247 communities (126 shown, 121 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 178 edges (avg confidence: 0.55)
- Token cost: 144,391 input · 0 output

## Community Hubs (Navigation)
- Root Scripts: Models
- Community: Views
- Analytics Dashboard & Products App
- Users: Views
- Orders App: Admin
- Products App
- Accessories App
- Orders App: Views
- Products App: Views
- Orders App: Serializers
- Products App: Views
- Root Scripts: Models
- Products App: Completion Logic
- Users: Tests
- Products App: Views
- Orders App: Admin
- Orders App: Models
- Products App
- Orders App: Models
- Orders App: Admin
- Products App
- Root Scripts
- Root Scripts
- Products App
- Products App
- Orders App: Models
- Root Scripts & Constellations Docs
- Orders App: Admin
- Products App
- Products App
- Root Scripts
- Root Scripts
- Orders App: Tests
- Products App
- Products App
- Products App
- Products App
- Products App
- Root Scripts
- Config
- Products App
- Payments: Views
- Products App
- Products App
- Products App
- Config
- Root Scripts
- Root Scripts
- Products App: Tests
- Root Scripts
- Root Scripts
- Root Scripts
- Products App
- Products App
- Root Scripts
- Root Scripts
- Root Scripts
- Products App: Tests
- Root Scripts
- Root Scripts
- Root Scripts
- Bible Updates
- Root Scripts
- Root Scripts
- Root Scripts
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App: Views
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Orders App: Admin
- Products App
- Products App
- Root Scripts
- Root Scripts
- Bible Updates
- Root Scripts
- Root Scripts
- Root Scripts
- Orders App: App Config
- Root Scripts
- Root Scripts
- Root Scripts
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Root Scripts
- Root Scripts
- Accessories App: App Config
- Analytics Dashboard: App Config
- Community: App Config
- Root Scripts
- Root Scripts
- Root Scripts
- Inventory: App Config
- Root Scripts
- Root Scripts
- Root Scripts
- Payments: App Config
- Products App: App Config
- Users: App Config
- Root Scripts
- Accessories App
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Community
- Community
- Config: ASGI Config
- Config: WSGI Config
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Orders App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Products App
- Root Scripts
- Root Scripts
- Root Scripts
- Root Scripts
- Users
- Users
- Users
- Users
- Clear stale .git/index.lock before every
- Unidentified alphanumeric ID note (produ
- Resend transactional email API configura

## God Nodes (most connected - your core abstractions)
1. `PokemonProduct` - 162 edges
2. `CardSet` - 99 edges
3. `Order` - 26 edges
4. `Era` - 21 edges
5. `OrderAdmin` - 20 edges
6. `ManualInvoiceAdmin` - 20 edges
7. `Category` - 18 edges
8. `ManualInvoice` - 17 edges
9. `OrderItem` - 15 edges
10. `ChecklistEntry` - 15 edges

## Surprising Connections (you probably didn't know these)
- `R2-only image hosting policy` --conceptually_related_to--> `Southern Hemisphere Constellations (compiled booklet)`  [INFERRED]
  CLAUDE.md → Southern Hemisphere Constellations/Southern_Hemisphere_Constellations.pdf
- `Reuse the _r2_client() credentials pattern for new R2 features` --references--> `upload_logos_to_r2()`  [EXTRACTED]
  CLAUDE.md → products/admin.py
- `admin/products/cardset/` --semantically_similar_to--> `PokeBulk sets tier system inclusion list`  [INFERRED] [semantically similar]
  products/Local Host url links.txt → graphify-out/converted/PokeBulk_Sets_Tier_Check_cd1e9fdd.md
- `R2 object storage credentials (PowerShell env vars)` --shares_data_with--> `Reuse the _r2_client() credentials pattern for new R2 features`  [INFERRED]
  products/R@.txt → CLAUDE.md
- `boto3 1.35.0 (S3-compatible client dependency)` --shares_data_with--> `Reuse the _r2_client() credentials pattern for new R2 features`  [INFERRED]
  requirements.txt → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **PokeMart API REST endpoint surface** — products_django_links_products_endpoint, products_django_links_products_by_set_endpoint, products_django_links_sets_endpoint, products_django_links_orders_endpoint, products_django_links_admin_panel, products_django_links_auth_login_endpoint, products_django_links_auth_profile_endpoint, products_django_links_payments_initiate_endpoint, products_django_links_payments_itn_endpoint, products_django_links_stock_update_endpoint, products_django_links_stock_wipe_endpoint [EXTRACTED 1.00]
- **Shared R2 credential/upload tooling across products** — upload_to_r2_r2client, upload_set_images_r2client, products_admin_r2client, products_admin_upload_logos_to_r2 [INFERRED 0.85]
- **Southern Hemisphere Constellations star chart set** — southern_hemisphere_constellations_crux, southern_hemisphere_constellations_centaurus, southern_hemisphere_constellations_scorpius, southern_hemisphere_constellations_sagittarius, southern_hemisphere_constellations_orion [EXTRACTED 1.00]

## Communities (247 total, 121 thin omitted)

### Community 0 - "Root Scripts: Models"
Cohesion: 0.05
Nodes (13): audit_image_gaps.py Read-only. For every CardSet, reports how many cards have a…, check_broken_attack_text.py Read-only diagnostic -- prints the raw stored…, check_pbl_cardset.py Read-only. Checks PBL's CardSet record for the…, cleanup_wrong_variants.py Cross-references every PokemonProduct row in PRE,…, Read-only diagnostic. Does NOT change anything in the database. For every…, diagnose_prizepack_pre_gaps.py Read-only, focused version of…, diagnose_total_cards_mismatches.py Root cause for Crown Zenith (CRZ) not…, Check ALL variant records against TCGCSV prices. For each card's productId,… (+5 more)

### Community 1 - "Community: Views"
Cohesion: 0.06
Nodes (67): BlockAdmin, FriendshipAdmin, MessageAdmin, register, The moderation queue -- newest first, unresolved surfaced by default via…, Read-only-in-practice audit trail (no add permission) -- useful when…, ReportAdmin, TradeRequestAdmin (+59 more)

### Community 2 - "Analytics Dashboard & Products App"
Cohesion: 0.06
Nodes (40): dashboard_page(), staff_member_required, _get_client(), get_conversion_summary(), get_daily_visits(), get_funnel(), Builds an authenticated GA4 Data API client from env-provided credentials., Returns [{date: 'YYYY-MM-DD', visitors: int, sessions: int}, ...] for the last… (+32 more)

### Community 3 - "Users: Views"
Cohesion: 0.08
Nodes (27): ChangePasswordSerializer, LoginSerializer, Meta, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, RegisterSerializer, UserSerializer, admin_customer_search() (+19 more)

### Community 4 - "Orders App: Admin"
Cohesion: 0.07
Nodes (19): BuyOrderItemInline, CartAdmin, ManualInvoiceAdmin, ManualInvoiceItemInline, OrderTrackingAdmin, register, Shared by both the manual "Email" button (email_invoice_view) and the automatic…, Site-account lookup for the POS screen's new "existing customer" search box… (+11 more)

### Community 5 - "Products App"
Cohesion: 0.07
Nodes (36): PokeBulk Sets Tier Check (converted from xlsx), PBL - Pitch Black set (Mega Evolution Era, 2026-07-01), Prize Pack Series excluded from tier system, PokeBulk sets tier system inclusion list, Local dev server launch commands (cd + runserver), Django Links (production API endpoint list), /admin/ - Django admin panel (production), POST /api/auth/login/ - obtain auth token (+28 more)

### Community 6 - "Accessories App"
Cohesion: 0.09
Nodes (18): AccessoryAdmin, display, register, Michael's full-access management screen -- unrestricted regardless of…, Command, compute_zar_price(), get_json(), get_usd_zar_rate() (+10 more)

### Community 7 - "Orders App: Views"
Cohesion: 0.11
Nodes (21): atomic, Order, OrderSerializer, AdminCustomerSalesSummaryView, AdminOrderListView, _build_invoice_html(), CartRemoveView, CheckoutView (+13 more)

### Community 8 - "Products App: Views"
Cohesion: 0.10
Nodes (29): ChecklistEntry, Meta, PokedexCollectionEntry, One row = one customer has ticked one card as owned, on the Checklists page.…, One row = one customer hit 100% on one tier of one set, for the first time.…, One row = one customer has marked one exact card/variant (a single…, SetCompletionEvent, checklist_admin_customer() (+21 more)

### Community 9 - "Orders App: Serializers"
Cohesion: 0.10
Nodes (15): Cart, CartItem, community_discount_percent(), Returns the discount percentage (e.g. Decimal('5.00')) this user currently…, Post-discount total -- this is what checkout actually charges. Deliberately…, AdminOrderListSerializer, CartItemSerializer, CartSerializer (+7 more)

### Community 10 - "Products App: Views"
Cohesion: 0.13
Nodes (17): diagnose_era_logos.py Read-only: compares every Era row's exact `name` (and…, Category, Era, PokemonType, CardSetSerializer, CategorySerializer, EraSerializer, Meta (+9 more)

### Community 11 - "Root Scripts: Models"
Cohesion: 0.05
Nodes (9): check_pbl_pricing_sync.py Read-only diagnostic. Checks whether PBL has the same…, cleanup_wrong_variants_sitewide.py Generalized version of…, clear_broken_template_text.py Companion to audit_broken_template_text.py.…, delete_confirmed_duplicate_variants.py Applies the DELETE bucket from…, fix_asc_pattern_variant_tagging.py Michael, 2026-08-01: "ASC was plugged Energy…, fix_ball_variant_tagging.py Root cause (Michael, 2026-08-01 -- spotted after…, fix_ex_variant_code.py Cards like "Meloetta EX", "Excadrill EX" are currently…, Computes PokemonProduct.legal_expanded for the whole catalog. Expanded format… (+1 more)

### Community 12 - "Products App: Completion Logic"
Cohesion: 0.14
Nodes (19): backfill_missing_completion_events.py Root cause (Michael, 2026-08-01):…, diagnose_unreachable_card_keys.py Michael, 2026-08-01: "how come i don't 100%…, _broke_base_progress(), compute_set_completion(), compute_user_set_completion(), _fallback_display_num(), get_set_card_map(), is_set_eligible() (+11 more)

### Community 13 - "Users: Tests"
Cohesion: 0.12
Nodes (7): AbstractUser, UserAdmin, CustomUserAdmin, register, User, AuthTests, APITestCase

### Community 14 - "Products App: Views"
Cohesion: 0.14
Nodes (19): csrf_exempt, _build_manage_set_dropdown_html(), bundle_stock_entry(), checklist_stock(), delete_product(), manage_set(), require_GET, require_POST (+11 more)

### Community 15 - "Orders App: Admin"
Cohesion: 0.11
Nodes (6): Media, OrderAdmin, Paid' indicator, decoupled from payment_method (2026-08-14) -- Michael:…, Live total = subtotal of current line items + shipping_cost, calculated the…, Custom admin widget for Order.status. The real <select name="status"…, StatusStepperWidget

### Community 16 - "Orders App: Models"
Cohesion: 0.12
Nodes (6): BuyOrder, BuyOrderItem, ManualInvoiceItem, Meta, Automatic stock restoration on cancellation, and re-decrement if an order is…, direction=+1 restores stock (order cancelled), direction=-1 re-reserves it…

### Community 17 - "Products App"
Cohesion: 0.16
Nodes (10): clean_card_name(), clean_rarity(), Command, get_era(), make_filename(), BaseCommand, Management command: download_card_images…, Return a filename-safe rarity label from DB rarity value. (+2 more)

### Community 18 - "Orders App: Models"
Cohesion: 0.15
Nodes (9): manage_set(), staff_member_required, OrderItem, receiver, Deleting a sold item (or the whole invoice it belongs to) puts the stock back.…, Deleting a bought item (or the whole buy order) takes it back out of pos_stock.…, restore_pos_stock_on_buy_order_item_delete(), restore_stock_on_manual_invoice_item_delete() (+1 more)

### Community 19 - "Orders App: Admin"
Cohesion: 0.13
Nodes (5): BuyOrderAdmin, build_buy_order_html(), html_to_pdf(), Buy order HTML + PDF builder. Mirrors manual_invoice.py's structure and…, Converts buy order HTML to PDF bytes using xhtml2pdf -- same helper as…

### Community 20 - "Products App"
Cohesion: 0.21
Nodes (14): Command, fetch_with_retry(), get_asc_ball(), get_best_price(), get_era_for_set(), get_japanese_name(), get_label(), get_set_config() (+6 more)

### Community 21 - "Root Scripts"
Cohesion: 0.24
Nodes (15): apply_watermark(), best_font_size(), clean_jpeg_bytes(), extract_card_number(), fetch_base_image(), get_limitless_image_url(), get_r2_client(), get_serebii_image_url() (+7 more)

### Community 22 - "Root Scripts"
Cohesion: 0.19
Nodes (15): build_titles(), clean_name(), clean_number(), enrich_card(), fetch_wikitext(), main(), name_to_url(), parse_wikitext() (+7 more)

### Community 23 - "Products App"
Cohesion: 0.23
Nodes (12): apply_to_product(), build_page_title(), clean_name(), Command, extract_template_block(), fetch_bulba_wikitext(), fetch_tcgcsv_numbers(), get_alternate_titles() (+4 more)

### Community 24 - "Products App"
Cohesion: 0.15
Nodes (5): FakeEra, FakeManager, FakePokemonProduct, FakeQuerySet, FakeSet

### Community 25 - "Orders App: Models"
Cohesion: 0.18
Nodes (7): ManualInvoice, ManualInvoiceListSerializer, Manual Invoice had zero REST API before this -- it only ever existed as Django…, AdminManualInvoiceListView, AdminManualInvoiceStatusUpdateView, Manual Invoice's first REST API (2026-08-12) -- read-only, feeds the staff…, PATCH-only status update for a Manual Invoice (2026-08-12) -- Michael: "Manual…

### Community 26 - "Root Scripts & Constellations Docs"
Cohesion: 0.21
Nodes (13): Reuse the _r2_client() credentials pattern for new R2 features, R2-only image hosting policy, _r2_client() in products/admin.py, R2 object storage credentials (PowerShell env vars), boto3 1.35.0 (S3-compatible client dependency), Centaurus (The Centaur) star chart, Crux (The Southern Cross) star chart, Orion (The Hunter) star chart (+5 more)

### Community 27 - "Orders App: Admin"
Cohesion: 0.19
Nodes (8): OrderItemInline, OrderTrackingInline, OrderTracking, create_tracking_on_status_change(), receiver, Automated, simple status-update email to the customer whenever an order's…, send_manual_invoice_status_email(), _send_status_update_email()

### Community 28 - "Products App"
Cohesion: 0.24
Nodes (10): clean_base_name(), Command, effective_mark(), is_basic_energy(), is_trainer(), _lower(), mark_is_legal(), BaseCommand (+2 more)

### Community 29 - "Products App"
Cohesion: 0.22
Nodes (7): build_variant_map(), Command, get_era(), make_filename(), BaseCommand, Management command: generate_variant_images…, Build descriptive filename. e.g. ASC-001-Ericas-Oddish.png or ASC-001-Ericas-…

### Community 30 - "Root Scripts"
Cohesion: 0.26
Nodes (11): build_bible(), ext(), fetch(), get_live_zar_rate(), is_card(), pokebulk_price(), PokéBulk SA — TCGCSV Master Bible Builder…, Extract value from extendedData by key name. (+3 more)

### Community 31 - "Root Scripts"
Cohesion: 0.29
Nodes (11): fetch_all_sets(), fetch_group(), fetch_json(), fetch_prices(), flatten_product(), main(), PokeBulk SA — TCGCSV Full Product Fetch v1.0.0 Fetches ALL product data from…, Fetch the full set list from TCGCSV and process each group. (+3 more)

### Community 32 - "Orders App: Tests"
Cohesion: 0.17
Nodes (3): CartTests, CheckoutTests, APITestCase

### Community 33 - "Products App"
Cohesion: 0.17
Nodes (10): clean_name(), Command, fetch_tcgcsv_products(), find_original_card(), parse_card_num(), BaseCommand, Fetch all products from TCGCSV group, Extract card number integer from 006/163 -> 6 (+2 more)

### Community 34 - "Products App"
Cohesion: 0.29
Nodes (9): Command, fetch_all_cards(), fetch_set_info(), generate_excel(), generate_pdf(), get_headers(), output_dir(), BaseCommand (+1 more)

### Community 35 - "Products App"
Cohesion: 0.29
Nodes (9): Command, fetch_all_cards(), fetch_set_info(), generate_excel(), generate_pdf(), get_headers(), output_dir(), BaseCommand (+1 more)

### Community 36 - "Products App"
Cohesion: 0.24
Nodes (9): Command, get_era_code(), import_row(), parse_legal(), BaseCommand, PokéBulk SA — Bible Import Management Command Place in:…, Import a single row. Called inside its own transaction.atomic() block., safe_decimal() (+1 more)

### Community 37 - "Products App"
Cohesion: 0.24
Nodes (9): Command, _ext(), _get_rate(), _parse_number(), BaseCommand, sync_tcgcsv - PokeBulk SA Syncs cards from TCGCSV into Railway DB. - productId…, Convert USD to ZAR with markup, round UP to nearest R0.50, min R1.50, _sync_group() (+1 more)

### Community 38 - "Root Scripts"
Cohesion: 0.24
Nodes (5): Command, BaseCommand, Syncs CatalogProduct + TCGCSVSource directly from TCGCSV -- no dependency on…, Lowercase, hyphenated, safe for a SKU segment. 'x' fallback so an empty/missing…, slugify_part()

### Community 39 - "Config"
Cohesion: 0.20
Nodes (8): _ipv4_get_socket(), IPv4EmailBackend, IPv4SMTP, IPv4SMTP_SSL, Forces outbound SMTP connections over IPv4. Railway's containers frequently…, Replaces smtplib's default socket creation -- which tries every address family…, Identical to Django's built-in SMTP backend -- copied from Django's own open()…, DjangoSMTPEmailBackend

### Community 40 - "Products App"
Cohesion: 0.22
Nodes (4): Command, parse_attack(), parse_weakness(), BaseCommand

### Community 41 - "Payments: Views"
Cohesion: 0.24
Nodes (5): method_decorator, generate_payfast_signature(), PayFastInitView, PayFastITNView, APIView

### Community 42 - "Products App"
Cohesion: 0.27
Nodes (7): Command, fetch_ptcgio_cards(), fetch_tcgcsv_images(), parse_num(), BaseCommand, enrich_only.py - PokeBulk SA Sources: 1. pokemontcg.io — primary: images,…, Fetch product imageUrl map from TCGCSV: {product_id: image_url}

### Community 43 - "Products App"
Cohesion: 0.27
Nodes (7): Command, get_or_create_era(), get_or_create_set(), norm_number(), BaseCommand, rebuild_from_tcgcsv.py ====================== PokéBulk SA — TCGCSV Master…, 018/172 → 18, TG01/TG30 → TG01, SWSH001 → SWSH001

### Community 44 - "Products App"
Cohesion: 0.27
Nodes (7): Command, fetch(), get_live_zar_rate(), pokebulk_price(), BaseCommand, PokéBulk SA — Daily Price Sync ================================ Django…, market_usd × zar_rate × 1.10, min R1.50, round UP to R0.50

### Community 45 - "Config"
Cohesion: 0.33
Nodes (4): BaseEmailBackend, MailerSendBackend, Handles both 'email@x.com' and 'Display Name <email@x.com>' formats., Converts a Django EmailMessage/EmailMultiAlternatives into MailerSend's JSON…

### Community 46 - "Root Scripts"
Cohesion: 0.36
Nodes (8): ext(), extract_variant(), get_rate(), main(), parse_card_number(), fetch_ball_variants.py Fetches ball variant products from TCGCSV for ASC, BLK,…, Extract variant from product name like 'Erika Oddish (Poke Ball), zar_price()

### Community 47 - "Root Scripts"
Cohesion: 0.42
Nodes (8): build_rows(), fetch_json(), fetch_prices(), get_group_name(), main(), parse_card_number(), 005/086' -> 5.0 ; '' or unparsable ->, Best-effort lookup of the TCGCSV group name, for logging only.

### Community 49 - "Root Scripts"
Cohesion: 0.32
Nodes (5): Command, fetch_cards(), parse_num(), BaseCommand, enrich_only.py - PokeBulk SA Verifies pokemontcg.io mapping before enriching.…

### Community 50 - "Root Scripts"
Cohesion: 0.43
Nodes (7): clean_name(), parse_variant(), Returns (is_holo_rare, number, display_name) for grouping/fetch purposes., strip_trailing_decorations(), try_get(), verify_and_fetch_group(), work()

### Community 51 - "Root Scripts"
Cohesion: 0.32
Nodes (7): get_live_zar_rate(), pokebulk_price(), price_card(), PokéBulk SA — Pricing Utility ============================== Live USD/ZAR rate…, Full price calculation for a card variant. Fetches live ZAR rate if not…, Fetch live USD/ZAR exchange rate. Tries 3 free sources in order — returns first…, Calculate the PokéBulk retail price in ZAR for a card variant. Formula: 1. raw…

### Community 52 - "Products App"
Cohesion: 0.25
Nodes (6): Command, fetch_all_cards_for_set(), parse_card_number(), BaseCommand, Extract the leading integer from pokemontcg.io's number field, e.g. '025' ->…, Paginate through every card in a set -- never sample just one. Retries with…

### Community 53 - "Products App"
Cohesion: 0.32
Nodes (4): Command, parse_attack(), parse_weakness(), BaseCommand

### Community 54 - "Root Scripts"
Cohesion: 0.39
Nodes (7): compute_pokebulk_zar(), get_json(), get_usd_zar_rate(), is_pokemon_related(), main(), Pulls every Pokemon-related product under TCGCSV's "Card Sleeves" category…, 3-source fallback chain, matching the documented pricing pipeline.

### Community 55 - "Root Scripts"
Cohesion: 0.39
Nodes (7): clean(), main(), sync_bible_to_db.py — PokeBulk SA Syncs the Bible CSV to the Railway PostgreSQL…, # IMPORTANT: pb_id must include variant_code, not just product_id., to_bool(), to_decimal(), to_int()

### Community 56 - "Root Scripts"
Cohesion: 0.67
Nodes (6): fetch_all_sets(), fetch_group(), fetch_json(), fetch_prices(), flatten_product(), main()

### Community 58 - "Root Scripts"
Cohesion: 0.52
Nodes (6): clean_name(), parse_variant(), strip_trailing_decorations(), try_get(), verify_and_fetch_group(), work()

### Community 59 - "Root Scripts"
Cohesion: 0.43
Nodes (6): is_cloudinary_url(), main(), make_public_id(), Upload image to Cloudinary and return new URL, Generate a unique Cloudinary public ID for a card, upload_image()

### Community 60 - "Root Scripts"
Cohesion: 0.60
Nodes (5): candidates_for(), clean_candidate(), main(), Returns a list of 1 or 2 cleaned candidate names -- 2 for tag-team ("X & Y")…, strip_trailing_decorations()

### Community 61 - "Bible Updates"
Cohesion: 0.67
Nodes (5): candidates_for(), clean_candidate(), main(), pad(), strip_trailing_decorations()

### Community 63 - "Root Scripts"
Cohesion: 0.47
Nodes (5): fetch_page(), main(), parse_serebii_html(), PokeBulk SA -- Serebii Enrichment Script…, Extraction built directly against CONFIRMED real HTML (Mega Darkrai ex, PBL…

### Community 64 - "Root Scripts"
Cohesion: 0.47
Nodes (5): find_home_by_denominator(), official_candidates_for(), Links every PRIZEPACK product to its "home set" printing: - Copies…, Returns the confirmed home set_code for product p, or None., resolve_home_code()

### Community 65 - "Products App"
Cohesion: 0.33
Nodes (4): Command, fetch_tcgcsv_images(), BaseCommand, Fetch product imageUrl map from TCGCSV: {product_id: image_url}

### Community 66 - "Products App"
Cohesion: 0.40
Nodes (3): Command, parse_sku(), BaseCommand

### Community 67 - "Products App"
Cohesion: 0.33
Nodes (4): Command, get_card_filename(), BaseCommand, Build the correct filename for a card based on set-specific rules. Returns just…

### Community 68 - "Products App"
Cohesion: 0.33
Nodes (4): get_checklist_url(), pokemon.com checklist PDF URLs mapped to Pokémon TCG API set codes. Use…, Returns (url, confidence) for a given API set code, or None if not mapped., verify_checklists.py Run from anywhere: python verify_checklists.py HEAD-checks…

### Community 69 - "Products App"
Cohesion: 0.40
Nodes (5): card_lookup(), card_search(), api_view, GET /api/cards/lookup/?sku=sv09-074-rev Called by PoBuSA (pobusa/services.py…, GET /api/cards/search/?q=gastly+sf Called by PoBuSA's buy-in screen — returns…

### Community 71 - "Root Scripts"
Cohesion: 0.53
Nodes (5): find_file(), get_r2_client(), main(), Search for filename in root and all subdirectories., upload_file()

### Community 72 - "Root Scripts"
Cohesion: 0.80
Nodes (4): candidates_for(), clean_candidate(), main(), strip_trailing_decorations()

### Community 73 - "Root Scripts"
Cohesion: 0.80
Nodes (4): candidates_for(), clean_candidate(), main(), strip_trailing_decorations()

### Community 74 - "Root Scripts"
Cohesion: 0.70
Nodes (4): get_r2_client(), main(), safe_filename(), try_download()

### Community 75 - "Root Scripts"
Cohesion: 0.70
Nodes (4): get_r2_client(), main(), safe_filename(), try_download()

### Community 76 - "Root Scripts"
Cohesion: 0.50
Nodes (4): fetch_set_images(), main(), enrich_images_ptcgio.py Fetches better images from pokemontcg.io for cards that…, Fetch all cards for a pokemontcg.io set, return dict of number -> image_url

### Community 77 - "Root Scripts"
Cohesion: 0.70
Nodes (4): clean_name(), strip_trailing_decorations(), try_get(), verify_and_fetch()

### Community 78 - "Root Scripts"
Cohesion: 0.60
Nodes (4): clean_name(), Returns (image_bytes, None) on a verified match, or (None, reason) otherwise., try_get(), verify_and_fetch()

### Community 79 - "Root Scripts"
Cohesion: 0.80
Nodes (4): candidates_for(), clean_candidate(), main(), strip_trailing_decorations()

### Community 80 - "Root Scripts"
Cohesion: 0.60
Nodes (4): clean_name(), Returns (image_bytes, None) on a verified match, or (None, reason) otherwise., try_get(), verify_and_fetch()

### Community 81 - "Root Scripts"
Cohesion: 0.70
Nodes (4): clean_name(), strip_trailing_decorations(), try_get(), verify_and_fetch()

### Community 82 - "Root Scripts"
Cohesion: 0.70
Nodes (4): clean_name(), strip_trailing_decorations(), try_get(), verify_and_fetch()

### Community 83 - "Root Scripts"
Cohesion: 0.70
Nodes (4): get_price_for_variant(), load_tcgcsv_flat_files(), main(), merge()

### Community 84 - "Root Scripts"
Cohesion: 0.70
Nodes (4): get_prices(), load_tcgcsv(), main(), merge()

### Community 87 - "Products App"
Cohesion: 0.40
Nodes (3): backfill_caught_for_pokedex_number(), Migration, Every row that exists before this migration was written under the old "one…

### Community 88 - "Root Scripts"
Cohesion: 0.40
Nodes (3): r2_key_from_url(), refresh_pbl_images.py Pitch Black (PBL) card images were originally scraped…, Extract the R2 object key from a full CDN URL, e.g.…

### Community 90 - "Bible Updates"
Cohesion: 0.67
Nodes (4): Bible Pokedex Backfill Report, final_pokedex reference dataset, Name-matcher backfill algorithm, Flagged wrong national-ID list (399 numeric IDs)

### Community 92 - "Root Scripts"
Cohesion: 0.67
Nodes (3): export_category(), fetch_prices(), Exports a full CSV snapshot of every product across the confirmed game…

### Community 95 - "Root Scripts"
Cohesion: 0.50
Nodes (3): card_lookup(), api_view, GET /api/cards/lookup/?sku=sv09-074-rev Called by PoBuSA (pobusa/services.py…

### Community 96 - "Root Scripts"
Cohesion: 0.50
Nodes (3): card_lookup(), api_view, GET /api/cards/lookup/?sku=sv09-074-rev Called by PoBuSA (pobusa/services.py…

### Community 97 - "Root Scripts"
Cohesion: 0.50
Nodes (3): card_lookup(), api_view, GET /api/cards/lookup/?sku=sv09-074-rev Called by PoBuSA (pobusa/services.py…

### Community 98 - "Products App"
Cohesion: 0.67
Nodes (3): apply_prices.py =============== PokéBulk SA — Direct price update from local…, round_up_50c(), to_zar()

### Community 110 - "Products App"
Cohesion: 0.50
Nodes (3): get_checklist_url(), pokemon.com checklist PDF URLs mapped to Pokémon TCG API set codes. Use…, Returns (url, confidence) for a given API set code, or None if not mapped.

### Community 111 - "Root Scripts"
Cohesion: 0.67
Nodes (3): get_client(), main(), upload_energy_symbols.py Uploads the 11 energy-type symbol PNGs from the local…

### Community 112 - "Root Scripts"
Cohesion: 0.50
Nodes (3): experimentalServices, web, routePrefix

## Ambiguous Edges - Review These
- `Bible Pokedex Backfill Report` → `Flagged wrong national-ID list (399 numeric IDs)`  [AMBIGUOUS]
  wrong_n_ids.txt · relation: conceptually_related_to

## Knowledge Gaps
- **88 isolated node(s):** `Migration`, `Meta`, `Meta`, `Migration`, `Migration` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **121 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Bible Pokedex Backfill Report` and `Flagged wrong national-ID list (399 numeric IDs)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `PokemonProduct` connect `Root Scripts: Models` to `Root Scripts`, `Community: Views`, `Root Scripts`, `Orders App: Admin`, `Analytics Dashboard & Products App`, `Root Scripts`, `Orders App: Views`, `Products App: Views`, `Users: Views`, `Products App: Views`, `Root Scripts: Models`, `Products App: Completion Logic`, `Root Scripts`, `Users: Tests`, `Root Scripts`, `Products App: Views`, `Products App`, `Orders App: Models`, `Root Scripts`, `Root Scripts`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App: Tests`, `Root Scripts`, `Root Scripts`, `Products App`, `Root Scripts`, `Products App: Tests`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Products App`, `Products App: Views`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Products App`, `Products App`, `Products App`, `Products App`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`?**
  _High betweenness centrality (0.218) - this node is a cross-community bridge._
- **Why does `CardSet` connect `Root Scripts: Models` to `Community: Views`, `Root Scripts`, `Analytics Dashboard & Products App`, `Products App: Views`, `Products App: Views`, `Products App: Completion Logic`, `Users: Tests`, `Products App: Views`, `Root Scripts`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App`, `Products App: Tests`, `Root Scripts`, `Root Scripts`, `Products App`, `Root Scripts`, `Products App: Tests`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`, `Root Scripts`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `PokemonProduct` (e.g. with `get_set_card_map()` and `PokemonProductSerializer`) actually correct?**
  _`PokemonProduct` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `CardSet` (e.g. with `compute_set_completion()` and `compute_user_set_completion()`) actually correct?**
  _`CardSet` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Order` (e.g. with `OrderAdmin` and `AdminOrderListSerializer`) actually correct?**
  _`Order` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `Era` (e.g. with `EraAdminForm` and `EraSerializer`) actually correct?**
  _`Era` has 5 INFERRED edges - model-reasoned connections that need verification._