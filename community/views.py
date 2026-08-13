# pokemart-api: community/views.py
#
# Customer community feature (2026-08-07): public Pokedex-collection/wishlist
# profiles, a browse directory, a "most wanted" demand board, direct
# messaging, trade requests, and block/report. Function-based @api_view
# views throughout, manual Response dicts rather than DRF serializers --
# matches the existing style in products/views.py and users/views.py rather
# than introducing a new pattern for just this feature.
#
# Privacy decisions made while building this (flagging explicitly rather
# than burying them):
#   - Public profiles are looked up by numeric user id, never by username --
#     mirrors the existing checklist_public design ("Shown on leaderboards
#     instead of the real username"), since username is customer-chosen and
#     may be a real name/email-like string.
#   - Collection VALUE (Rand amount) is deliberately never exposed on a
#     public profile, only item counts -- broadcasting exactly how much
#     cardboard someone has at home is a real-world safety concern (a
#     target list for theft), not just a business one. The customer's own
#     private /pokedex page still shows their own value to themselves.
#   - Every visibility gate re-checks BOTH community_profile_public AND a
#     non-blank public_display_name, same double-check the existing
#     checklist leaderboard/Wall of Honour use -- an opted-in customer who
#     never set a display name still shouldn't leak their real username.

import logging
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from products.completion import TIER_LABELS, TIER_ORDER
from products.models import PokemonProduct, PokedexCollectionEntry, SetCompletionEvent, CardSet, ChecklistEntry
from products.serializers import PokemonProductSerializer
from users.views import check_rate_limit
from .models import Block, TradeRequest, Message, Report, Friendship

User = get_user_model()
logger = logging.getLogger(__name__)


def _notify_new_message_email(message):
    """Best-effort email nudge for a new DM/trade message (2026-08-07,
    Michael: "Yes you can add email notifications"). Wrapped in
    try/except -- a failed notification must never break the actual message
    send, same rule as every other email call site in this codebase (e.g.
    orders/signals.py's status-update email). Rate-limited to one
    notification per (sender, recipient) pair per 15 minutes so a fast
    back-and-forth chat sends one email, not one per message -- reuses the
    same cache-based limiter as login/password-reset/community rate limits."""
    recipient = message.recipient
    if not recipient.email:
        return
    allowed, _ = check_rate_limit(
        f"community_msg_email:{message.sender_id}:{recipient.id}", limit=1, window_seconds=900,
    )
    if not allowed:
        return
    try:
        sender_name = message.sender.public_display_name or message.sender.username
        site_url = getattr(settings, 'SITE_URL', 'https://pokebulk.co.za')
        thread_url = f"{site_url}/messages/{message.sender_id}"
        preview = message.body[:200]

        subject = f'New message from {sender_name} on PokeBulk SA'
        text_body = (
            f"Hi {recipient.first_name or recipient.username},\n\n"
            f"{sender_name} sent you a message on PokeBulk SA:\n\n"
            f"\"{preview}\"\n\n"
            f"Reply here: {thread_url}\n\n"
            f"-- PokeBulk SA\n\n"
            f"You're getting this because messaging is turned on in your profile. "
            f"Turn it off anytime at {site_url}/profile."
        )
        html_body = f'''<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#222;padding:20px">
<h2 style="color:#ff6b35">New message from {sender_name}</h2>
<p>Hi {recipient.first_name or recipient.username},</p>
<p>{sender_name} sent you a message on PokeBulk SA:</p>
<p style="background:#f5f5f5;border-radius:8px;padding:12px 16px;font-style:italic">&quot;{preview}&quot;</p>
<p><a href="{thread_url}" style="background:#ff6b35;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block">Reply</a></p>
<p style="font-size:12px;color:#888">You're getting this because messaging is turned on in your profile. Turn it off anytime in your profile settings.</p>
<p style="font-size:12px;color:#888">-- PokeBulk SA</p>
</body></html>'''

        email = EmailMultiAlternatives(subject=subject, body=text_body, to=[recipient.email])
        email.attach_alternative(html_body, 'text/html')
        email.send(fail_silently=False)
        logger.info(
            "Community message notification email sent to user_id=%s from user_id=%s",
            recipient.id, message.sender_id,
        )
    except Exception:
        logger.exception(
            "Failed to send community message notification email to user_id=%s from user_id=%s",
            recipient.id, message.sender_id,
        )


def _avatar_url(user, request):
    if user.avatar:
        return request.build_absolute_uri(user.avatar.url)
    return None


def _public_card(user, request):
    """Shared shape for 'who is this' across every endpoint below.

    BUG FIX 2026-08-12 (Michael: "Community not working 100% new customer
    tried last night, not linking up"): display_name used to be
    user.public_display_name with NO fallback -- blank for anyone who
    hasn't opted into picking one, which rendered as a blank name on a
    friend's card (the actual bug: two customers had already become
    friends, but the new one never set a display name, so their entry on
    the Friends tab showed as nothing but an icon). Safe to fall back to
    username here globally: community_browse/most_wanted already exclude
    blank-display-name users from their querysets before ever calling this,
    so this fallback only ever kicks in for friends/pending lists and a
    friend's profile page -- exactly the contexts where the viewer already
    has a legitimate, consented relationship with this person and isn't
    being shown a stranger who chose to stay unnamed.
    """
    return {
        "id": user.id,
        "display_name": user.public_display_name or user.username,
        "avatar": _avatar_url(user, request),
        "trainer_level": user.trainer_level,
        "community_bio": user.community_bio,
        "messaging_enabled": user.messaging_enabled,
    }


def _is_blocked_either_way(user_id_a, user_id_b):
    return Block.objects.filter(
        Q(user_id=user_id_a, blocked_user_id=user_id_b) |
        Q(user_id=user_id_b, blocked_user_id=user_id_a)
    ).exists()


def _are_friends(user_id_a, user_id_b):
    """Symmetric -- doesn't matter who originally sent the request, only
    that it's in the 'accepted' state."""
    return Friendship.objects.filter(
        Q(from_user_id=user_id_a, to_user_id=user_id_b) |
        Q(from_user_id=user_id_b, to_user_id=user_id_a),
        status="accepted",
    ).exists()


def _friendship_status(viewer_id, other_id):
    """Relative to the viewer: 'self', 'friends', 'pending_sent',
    'pending_received', or 'none'."""
    if viewer_id is None:
        return "none"
    if viewer_id == other_id:
        return "self"
    fr = Friendship.objects.filter(
        Q(from_user_id=viewer_id, to_user_id=other_id) |
        Q(from_user_id=other_id, to_user_id=viewer_id)
    ).first()
    if not fr:
        return "none"
    if fr.status == "accepted":
        return "friends"
    if fr.status == "pending":
        return "pending_sent" if fr.from_user_id == viewer_id else "pending_received"
    return "none"  # declined -- treated as if nothing ever happened, can re-request


_TIER_RANK = {t: i for i, t in enumerate(TIER_ORDER)}
_TIER_RANK['complete_set'] = len(TIER_ORDER)


def _best_completions_for_user(user):
    """Same source of truth and same 'highest tier per set' logic as
    products.views.checklist_my_completions, just for an arbitrary user
    instead of always request.user -- reuses SetCompletionEvent so this can
    never drift out of sync with what the Wall of Honour counts as
    'complete'. Returns a list (not a dict) since this is for display, with
    set names resolved for convenience."""
    events = SetCompletionEvent.objects.filter(user=user).values_list('card_set', 'tier')
    best = {}
    for card_set, tier in events:
        current = best.get(card_set)
        if current is None or _TIER_RANK.get(tier, -1) > _TIER_RANK.get(current, -1):
            best[card_set] = tier
    if not best:
        return []
    sets_by_code = {s.code: s for s in CardSet.objects.filter(code__in=best.keys())}
    return [
        {
            "set_code": code,
            "set_name": sets_by_code[code].name if code in sets_by_code else code,
            "tier": tier,
            "tier_label": TIER_LABELS.get(tier, tier),
        }
        for code, tier in sorted(best.items())
    ]


def _visible_profile_or_404(user_id, viewer_id=None):
    """The one gate every public-profile-reading endpoint uses. A profile is
    visible if EITHER: (a) opted into general public browsing
    (community_profile_public) -- same double-check as the checklist
    leaderboard, needs a display name too, or (b) the viewer is an accepted
    friend of this user, regardless of the public toggle -- friendship is a
    stronger, more deliberate grant than "browsable by anyone" (2026-08-07,
    Michael: friends should "share their collections amongst themselves"
    even if they're not broadcasting to the whole Community directory).

    BUG FIX 2026-08-12 (Michael: "Community not working 100% new customer
    tried last night, not linking up"): the display-name requirement used
    to apply BEFORE the friendship check (via .exclude(public_display_name=
    "") on the initial lookup), so a friend who'd never set a display name
    404'd here every time -- their profile was literally unreachable despite
    being an accepted friend, exactly contradicting the "stronger grant"
    this function is meant to give friends. Friendship is now checked
    first, with no display-name requirement at all; the blank-name
    exclusion only still applies to the public_community_profile path,
    which is the one actually meant to require picking a name before
    strangers can find you."""
    user = get_object_or_404(User, pk=user_id)
    if viewer_id is not None and _are_friends(viewer_id, user.id):
        return user
    if user.community_profile_public and user.public_display_name:
        return user
    # Not public and not a friend -- 404, same as "doesn't exist" from the
    # outside, don't leak that this account exists but is just private.
    from django.http import Http404
    raise Http404


@api_view(['GET'])
@permission_classes([AllowAny])
def public_profile(request, user_id):
    """A customer's community profile. Three independent visibility layers,
    each opted into separately:
      - community_profile_public: summary Pokedex stats + recent 6 catches
        + wishlist -- what gives strangers browsing Community "a reason to
        look" (Michael, 2026-08-07).
      - checklist_public: per-set tier completion list (same data source as
        the leaderboard/Wall of Honour).
      - Being FRIENDS with the viewer: unlocks the FULL interactive Pokedex
        (every caught species + card art, enough to drive the same
        Gen-tabbed grid Michael sees for his own /pokedex), regardless of
        whether community_profile_public/checklist_public are on -- the
        stronger, more deliberate grant.
    Collection VALUE in Rand is never included via this endpoint, full stop,
    friend or not -- see the module docstring for why.
    GET /api/community/profile/<user_id>/"""
    viewer_id = request.user.id if request.user.is_authenticated else None
    user = _visible_profile_or_404(user_id, viewer_id=viewer_id)
    is_friend = viewer_id is not None and _are_friends(viewer_id, user.id)

    entries = list(
        PokedexCollectionEntry.objects.filter(user=user)
        .select_related('product')
        .order_by('-added_at')
    )
    species = set()
    best_image_by_species = {}
    for e in entries:
        pn = e.caught_for_pokedex_number or e.product.pokedex_number
        if pn:
            species.add(pn)
            price = e.product.price or Decimal('0')
            if e.product.image_url and (pn not in best_image_by_species or price > best_image_by_species[pn][0]):
                best_image_by_species[pn] = (price, e.product.image_url)

    recently_added = entries[:6]
    wishlist_products = user.wishlist.select_related('card_set', 'card_set__era').all()

    payload = {
        **_public_card(user, request),
        "friendship_status": _friendship_status(viewer_id, user.id),
        "species_collected": len(species),
        "caught_pokedex_numbers": sorted(species),
        "recent_catches": PokemonProductSerializer(
            [e.product for e in recently_added], many=True, context={'request': request}
        ).data,
        "wishlist": PokemonProductSerializer(wishlist_products, many=True, context={'request': request}).data,
        "can_message": (
            viewer_id is not None
            and viewer_id != user.id
            and user.messaging_enabled
            and not _is_blocked_either_way(viewer_id, user.id)
        ),
        # Only ever non-empty when checklist_public is on -- matches the
        # leaderboard/Wall of Honour's own opt-in, independent of everything
        # else on this page.
        "checklist_completions": _best_completions_for_user(user) if user.checklist_public else [],
        "is_friend": is_friend,
    }

    if is_friend:
        # Full grid data -- same shape pokedex_my_collection returns for
        # yourself (minus collection_value, never exposed here), so the
        # frontend can feed it straight into the existing PokedexGrid
        # component instead of a second bespoke rendering path.
        payload["full_pokedex"] = {
            "caught_pokedex_numbers": sorted(species),
            "caught_card_images": {str(pn): url for pn, (_, url) in best_image_by_species.items()},
        }

        # Michael, 2026-08-08: "add the checklist to Friends access, so they
        # can share their sets that they have, also show what is needed" --
        # unlike checklist_completions above (best TIER per set, gated by
        # checklist_public and visible to any public-profile viewer), this is
        # the raw per-card checked/unchecked data, same shape
        # products.views.checklist_entries already returns for your OWN
        # account ({"ASC": ["001/217_N", ...], ...}). Friends-only, same
        # stronger-grant precedent as full_pokedex just above -- exact
        # per-card gaps are a more useful (and more sensitive) want-list than
        # the tier summary, so it doesn't piggyback on checklist_public.
        checklist_rows = ChecklistEntry.objects.filter(user=user).values('card_set', 'card_key')
        checklist_entries_by_set = {}
        for row in checklist_rows:
            checklist_entries_by_set.setdefault(row['card_set'], []).append(row['card_key'])
        payload["full_checklist"] = {"entries": checklist_entries_by_set}

    return Response(payload)


@api_view(['GET'])
@permission_classes([AllowAny])
def community_browse(request):
    """Directory of every opted-in public profile, newest-collection-first.
    GET /api/community/browse/?q=search"""
    qs = (
        User.objects.filter(community_profile_public=True)
        .exclude(public_display_name="")
        .annotate(
            species_count=Count('pokedex_entries__caught_for_pokedex_number', distinct=True),
            wishlist_count=Count('wishlist', distinct=True),
        )
    )
    q = (request.GET.get('q') or '').strip()
    if q:
        # BUG FIX 2026-08-12 (Michael: "Not adding up, customer has same
        # issue" -- searching by a customer's actual site username came up
        # empty even though their chosen public_display_name might be
        # something else entirely). Search used to only match
        # public_display_name, so anyone searching by the name/handle they
        # actually know a customer by -- their username, not whatever
        # display name that customer happened to pick -- got zero results
        # even though the profile is public and qualifies. Doesn't expose
        # anything new: this only changes which of the already-public,
        # already-named rows above get matched by a given search term.
        qs = qs.filter(Q(public_display_name__icontains=q) | Q(username__icontains=q))
    qs = qs.order_by('-species_count')[:60]

    return Response({
        "profiles": [
            {
                **_public_card(u, request),
                "species_collected": u.species_count,
                "wishlist_count": u.wishlist_count,
            }
            for u in qs
        ]
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def most_wanted(request):
    """Top products by wishlist count -- ONLY counting customers with a
    public community profile (Michael, 2026-08-08: "if person doesn't have
    public profile, don't add their cards to wishlist list... I don't know
    who is looking for that card, it will just add clutter on a page
    supposed to be used to help people ... from others that have public
    profiles"). Originally counted every wishlist site-wide as anonymous
    aggregate demand; changed because a card only a private wishlist wants
    isn't something anyone browsing Community can actually act on -- same
    double opt-in check (community_profile_public AND a real display name)
    every other public-profile-gated view already uses.
    GET /api/community/most-wanted/?limit=20"""
    try:
        limit = min(int(request.GET.get('limit', 20)), 100)
    except (TypeError, ValueError):
        limit = 20

    public_wisher = Q(
        wishlisted_by__community_profile_public=True,
    ) & ~Q(wishlisted_by__public_display_name="")

    qs = (
        PokemonProduct.objects.filter(is_active=True)
        .annotate(wanted_by=Count('wishlisted_by', filter=public_wisher, distinct=True))
        .filter(wanted_by__gt=0)
        .order_by('-wanted_by')[:limit]
    )
    return Response({
        "most_wanted": [
            {"wanted_by": p.wanted_by, **PokemonProductSerializer(p, context={'request': request}).data}
            for p in qs
        ]
    })


# ── Friends ──────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_request_send(request):
    """POST /api/community/friends/request/  body: {"to_user_id": 5}
    If to_user already sent ME a pending request, this auto-accepts it
    instead of creating a second row -- a mutual "I want to be friends with
    you too" shouldn't require the first person to separately go respond to
    their own now-redundant incoming request."""
    me = request.user
    to_user_id = request.data.get('to_user_id')
    if not to_user_id:
        return Response({'error': 'to_user_id is required'}, status=400)
    if str(to_user_id) == str(me.id):
        return Response({'error': "Can't friend yourself"}, status=400)

    to_user = get_object_or_404(User, pk=to_user_id)
    if _is_blocked_either_way(me.id, to_user.id):
        return Response({'error': 'Unable to contact this customer'}, status=403)
    if _are_friends(me.id, to_user.id):
        return Response({'error': 'Already friends'}, status=400)

    allowed, _ = check_rate_limit(f"community_friend_req:{me.id}", limit=30, window_seconds=3600)
    if not allowed:
        return Response({'error': 'Too many friend requests sent recently. Please try again later.'}, status=429)

    reverse_pending = Friendship.objects.filter(from_user=to_user, to_user=me, status='pending').first()
    if reverse_pending:
        reverse_pending.status = 'accepted'
        reverse_pending.save(update_fields=['status', 'updated_at'])
        return Response({'id': reverse_pending.id, 'status': 'accepted', 'auto_accepted': True})

    existing = Friendship.objects.filter(from_user=me, to_user=to_user).first()
    if existing:
        if existing.status == 'declined':
            existing.status = 'pending'
            existing.save(update_fields=['status', 'updated_at'])
            return Response({'id': existing.id, 'status': 'pending'}, status=201)
        return Response({'id': existing.id, 'status': existing.status})

    fr = Friendship.objects.create(from_user=me, to_user=to_user, status='pending')
    return Response({'id': fr.id, 'status': fr.status}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_request_respond(request, friendship_id):
    """POST /api/community/friends/<id>/respond/  body: {"action": "accept"|"decline"}
    Only the recipient (to_user) can respond."""
    fr = get_object_or_404(Friendship, pk=friendship_id, to_user=request.user)
    action = request.data.get('action')
    if action not in ('accept', 'decline'):
        return Response({'error': 'action must be "accept" or "decline"'}, status=400)
    if fr.status != 'pending':
        return Response({'error': f'This request is already {fr.status}'}, status=400)

    fr.status = 'accepted' if action == 'accept' else 'declined'
    fr.save(update_fields=['status', 'updated_at'])
    return Response({'id': fr.id, 'status': fr.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_remove(request):
    """POST /api/community/friends/remove/  body: {"user_id": 5}
    Removes an accepted friendship (either direction) or withdraws/declines
    a still-pending request between the two."""
    me = request.user
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    Friendship.objects.filter(
        Q(from_user=me, to_user_id=user_id) | Q(from_user_id=user_id, to_user=me)
    ).delete()
    return Response({'removed': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def friends_list(request):
    """GET /api/community/friends/ -> accepted friends + pending sent/received."""
    me = request.user
    accepted = Friendship.objects.filter(
        Q(from_user=me) | Q(to_user=me), status='accepted'
    ).select_related('from_user', 'to_user')
    pending_sent = Friendship.objects.filter(from_user=me, status='pending').select_related('to_user')
    pending_received = Friendship.objects.filter(to_user=me, status='pending').select_related('from_user')

    friends = []
    for fr in accepted:
        other = fr.to_user if fr.from_user_id == me.id else fr.from_user
        friends.append(_public_card(other, request))

    return Response({
        "friends": friends,
        "pending_sent": [
            {"id": fr.id, "user": _public_card(fr.to_user, request), "created_at": fr.created_at}
            for fr in pending_sent
        ],
        "pending_received": [
            {"id": fr.id, "user": _public_card(fr.from_user, request), "created_at": fr.created_at}
            for fr in pending_received
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_search(request):
    """GET /api/community/users/search/?q=placebo

    2026-08-12 -- Michael: "There is no way to search for users, to make
    friends?" There wasn't: the Trainers tab (community_browse) is the only
    existing search, and it deliberately only surfaces customers who've
    turned on community_profile_public AND picked a display name -- exactly
    right for "browse public collections", but it means two customers can't
    find each other to become friends at all until one of them opts into
    full public browsing first, which is a much bigger ask than "let me add
    a friend". This is a separate, friend-request-only search: matches by
    username (not display name -- a customer searching for someone
    generally knows their login handle, not a display name that person
    may not have set), no public-profile requirement, IsAuthenticated
    rather than AllowAny since this is for logged-in customers finding each
    other, not anonymous browsing. Blocked users (either direction) are
    excluded so a block is actually respected here too, same as everywhere
    else in this app.
    """
    me = request.user
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return Response({"results": []})

    blocked_by_me = Block.objects.filter(user=me).values_list('blocked_user_id', flat=True)
    blocking_me = Block.objects.filter(blocked_user=me).values_list('user_id', flat=True)
    exclude_ids = set(blocked_by_me) | set(blocking_me)
    exclude_ids.add(me.id)

    users = (
        User.objects.filter(Q(username__icontains=q) | Q(public_display_name__icontains=q))
        .exclude(id__in=exclude_ids)
        .order_by('username')[:20]
    )

    return Response({
        "results": [
            {
                **_public_card(u, request),
                "username": u.username,
                "friendship_status": _friendship_status(me.id, u.id),
            }
            for u in users
        ]
    })


# ── Messaging ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversations_list(request):
    """One row per other customer this user has ever exchanged messages
    with, most recent activity first. GET /api/community/conversations/"""
    me = request.user
    msgs = (
        Message.objects.filter(Q(sender=me) | Q(recipient=me))
        .select_related('sender', 'recipient')
        .order_by('-created_at')
    )
    by_other = {}
    for m in msgs:
        other = m.recipient if m.sender_id == me.id else m.sender
        if other.id not in by_other:
            unread = Message.objects.filter(sender=other, recipient=me, read_at__isnull=True).count()
            by_other[other.id] = {
                "other_user": _public_card(other, request),
                "last_message": {
                    "body": m.body, "created_at": m.created_at, "from_me": m.sender_id == me.id,
                },
                "unread_count": unread,
            }
    return Response({"conversations": list(by_other.values())})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_thread(request, user_id):
    """Full message history with one other customer, oldest first. Marks
    their unread messages to you as read as a side effect of viewing it.
    GET /api/community/conversations/<user_id>/"""
    other = get_object_or_404(User, pk=user_id)
    me = request.user
    thread = Message.objects.filter(
        Q(sender=me, recipient=other) | Q(sender=other, recipient=me)
    ).order_by('created_at')

    Message.objects.filter(sender=other, recipient=me, read_at__isnull=True).update(
        read_at=timezone.now()
    )

    return Response({
        "other_user": _public_card(other, request),
        "messages": [
            {
                "id": m.id, "body": m.body, "created_at": m.created_at,
                "from_me": m.sender_id == me.id,
                "trade_request_id": m.trade_request_id,
            }
            for m in thread
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request):
    """POST /api/community/messages/send/  body: {"to_user_id": 5, "body": "..."}
    A cold DM (no prior thread) requires the recipient to have opted in via
    messaging_enabled. A REPLY within an existing thread always goes through
    regardless of the recipient's current toggle state -- they clearly
    already engaged, and losing the ability to reply mid-conversation the
    moment someone flips a setting would be a confusing, unnecessary block."""
    me = request.user
    to_user_id = request.data.get('to_user_id')
    body = (request.data.get('body') or '').strip()
    if not to_user_id or not body:
        return Response({'error': 'to_user_id and body are required'}, status=400)
    if str(to_user_id) == str(me.id):
        return Response({'error': "Can't message yourself"}, status=400)

    # Basic anti-spam: 40 messages/hour per sender, same cache-based limiter
    # already used for login/password-reset. Generous enough for genuine
    # back-and-forth chat, tight enough to stop someone blasting every
    # public profile in the directory.
    allowed, _ = check_rate_limit(f"community_msg:{me.id}", limit=40, window_seconds=3600)
    if not allowed:
        return Response({'error': 'Too many messages sent recently. Please try again later.'}, status=429)

    to_user = get_object_or_404(User, pk=to_user_id)

    if _is_blocked_either_way(me.id, to_user.id):
        return Response({'error': 'Unable to send this message'}, status=403)

    existing_thread = Message.objects.filter(
        Q(sender=me, recipient=to_user) | Q(sender=to_user, recipient=me)
    ).exists()
    if not to_user.messaging_enabled and not existing_thread:
        return Response({'error': 'This customer is not accepting messages right now'}, status=403)

    trade_request_id = request.data.get('trade_request_id')
    msg = Message.objects.create(
        sender=me, recipient=to_user, body=body[:2000],
        trade_request_id=trade_request_id or None,
    )
    _notify_new_message_email(msg)
    return Response({
        "id": msg.id, "body": msg.body, "created_at": msg.created_at, "from_me": True,
    }, status=201)


# ── Trade requests ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trade_request_create(request):
    """POST /api/community/trade-requests/
    body: {"to_user_id": 5, "wanted_product_id": 123, "message": "..."}
    wanted_product_id is optional (a general opener), but when given it
    should normally be something from to_user's own wishlist -- not
    enforced server-side (a customer might reasonably offer something the
    other person hasn't listed yet), just a UI convention."""
    me = request.user
    to_user_id = request.data.get('to_user_id')
    if not to_user_id:
        return Response({'error': 'to_user_id is required'}, status=400)
    if str(to_user_id) == str(me.id):
        return Response({'error': "Can't send yourself a trade request"}, status=400)

    allowed, _ = check_rate_limit(f"community_trade:{me.id}", limit=20, window_seconds=3600)
    if not allowed:
        return Response({'error': 'Too many trade requests sent recently. Please try again later.'}, status=429)

    to_user = get_object_or_404(User, pk=to_user_id)
    if _is_blocked_either_way(me.id, to_user.id):
        return Response({'error': 'Unable to contact this customer'}, status=403)
    if not to_user.messaging_enabled:
        return Response({'error': 'This customer is not accepting messages right now'}, status=403)

    wanted_product_id = request.data.get('wanted_product_id')
    wanted_product = None
    if wanted_product_id:
        wanted_product = get_object_or_404(PokemonProduct, pk=wanted_product_id)

    message_body = (request.data.get('message') or '').strip()

    trade = TradeRequest.objects.create(
        from_user=me, to_user=to_user, wanted_product=wanted_product, message=message_body,
    )
    if message_body:
        trade_msg = Message.objects.create(
            sender=me, recipient=to_user, body=message_body[:2000], trade_request=trade,
        )
        _notify_new_message_email(trade_msg)
    return Response({
        "id": trade.id, "status": trade.status, "created_at": trade.created_at,
        "wanted_product_id": trade.wanted_product_id,
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trade_request_respond(request, trade_id):
    """POST /api/community/trade-requests/<id>/respond/  body: {"action": "accept"|"decline"}
    Only the recipient can respond. Posts a short system-style Message back
    into the thread so the sender sees the outcome without a separate
    notification channel."""
    trade = get_object_or_404(TradeRequest, pk=trade_id, to_user=request.user)
    action = request.data.get('action')
    if action not in ('accept', 'decline'):
        return Response({'error': 'action must be "accept" or "decline"'}, status=400)
    if trade.status != 'pending':
        return Response({'error': f'This trade request is already {trade.status}'}, status=400)

    trade.status = 'accepted' if action == 'accept' else 'declined'
    trade.save(update_fields=['status', 'updated_at'])

    note = "accepted your trade request! 🎉" if action == 'accept' else "declined your trade request."
    response_msg = Message.objects.create(
        sender=request.user, recipient=trade.from_user,
        body=f"{request.user.public_display_name or 'This trainer'} {note}",
        trade_request=trade,
    )
    _notify_new_message_email(response_msg)
    return Response({"id": trade.id, "status": trade.status})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trade_requests_list(request):
    """Everything sent to, or received by, this customer.
    GET /api/community/trade-requests/"""
    me = request.user
    sent = TradeRequest.objects.filter(from_user=me).select_related('to_user', 'wanted_product')
    received = TradeRequest.objects.filter(to_user=me).select_related('from_user', 'wanted_product')

    def _shape(t, other_field):
        other = getattr(t, other_field)
        return {
            "id": t.id, "status": t.status, "message": t.message, "created_at": t.created_at,
            "other_user": _public_card(other, request),
            "wanted_product": PokemonProductSerializer(t.wanted_product, context={'request': request}).data if t.wanted_product else None,
        }

    return Response({
        "sent": [_shape(t, 'to_user') for t in sent],
        "received": [_shape(t, 'from_user') for t in received],
    })


# ── Block / report ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def block_user(request):
    """POST /api/community/block/  body: {"user_id": 5}"""
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    target = get_object_or_404(User, pk=user_id)
    Block.objects.get_or_create(user=request.user, blocked_user=target)
    return Response({'blocked': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unblock_user(request):
    """POST /api/community/unblock/  body: {"user_id": 5}"""
    user_id = request.data.get('user_id')
    Block.objects.filter(user=request.user, blocked_user_id=user_id).delete()
    return Response({'blocked': False})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_user(request):
    """POST /api/community/report/
    body: {"reported_user_id": 5, "reason": "spam", "details": "...", "message_id": 123}
    Pure queue -- lands in Django admin for Michael to review, nothing here
    auto-actions the report."""
    reported_user_id = request.data.get('reported_user_id')
    reason = request.data.get('reason')
    valid_reasons = {c[0] for c in Report.REASON_CHOICES}
    if not reported_user_id or reason not in valid_reasons:
        return Response({'error': f'reported_user_id is required and reason must be one of {sorted(valid_reasons)}'}, status=400)

    allowed, _ = check_rate_limit(f"community_report:{request.user.id}", limit=10, window_seconds=3600)
    if not allowed:
        return Response({'error': 'Too many reports submitted recently. Please try again later.'}, status=429)

    reported_user = get_object_or_404(User, pk=reported_user_id)
    message_id = request.data.get('message_id')
    message = Message.objects.filter(pk=message_id).first() if message_id else None

    Report.objects.create(
        reporter=request.user, reported_user=reported_user, message=message,
        reason=reason, details=(request.data.get('details') or '').strip(),
    )
    return Response({'reported': True}, status=201)
