# pokemart-api: community/models.py
#
# Backing models for the customer community feature (2026-08-07): public
# Pokedex-collection/wishlist profiles, direct messaging, trade requests,
# and basic moderation (block/report). Deliberately its own app rather than
# folded into users/ or products/ -- it touches both (User <-> User
# messaging, User <-> PokemonProduct trade context) and is the kind of
# feature that's easiest to reason about, and to disable/rip out later if
# needed, as one self-contained unit.
#
# Design notes:
#   - No separate "Conversation" model. A conversation between two users is
#     derived on the fly (grouped by the unordered pair of sender/recipient)
#     from Message rows -- simplest thing that works for a DM inbox, and one
#     less table to keep in sync.
#   - TradeRequest and Message are related but independent: creating a trade
#     request also creates a Message (carrying the opening note) so the
#     whole exchange shows up in one place in the recipient's inbox, but a
#     TradeRequest can exist without further messages, and messages can
#     exist without any trade request attached (plain chat).
#   - Block is one-directional by design -- blocking isn't inherently mutual
#     (matches how blocking works on basically every other platform).
#   - Report is a pure queue for Michael to review in Django admin. Nothing
#     here auto-hides, auto-bans, or auto-removes anything -- moderation
#     stays a human decision.

from django.conf import settings
from django.db import models


class Friendship(models.Model):
    """One row = one friend REQUEST, which becomes a friendSHIP once
    accepted (2026-08-07, Michael: "give them the option to make friends
    and share their collections amongst themselves"). Directional at
    creation (from_user asked, to_user hasn't answered yet) but symmetric
    once accepted -- are_friends() below checks both directions, so it
    doesn't matter who originally sent the request.

    Being friends is a STRONGER visibility grant than community_profile_public
    on its own: it unlocks the full interactive Pokedex grid (every caught
    species + card art, browsable by Generation, same view Michael gets for
    himself) and the full per-set Checklist tier breakdown, regardless of
    whether the profile is opted into general public browsing. The public
    Community toggle is what gives strangers "a reason to look" (a taste --
    summary stats, recent catches, wishlist); friendship is what unlocks the
    real thing. Collection VALUE in Rand is still never exposed here either
    way -- see community/views.py for why.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_sent")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="friendships_received")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="unique_friendship_pair"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"], name="community_fr_to_status_idx"),
            models.Index(fields=["from_user", "status"], name="community_fr_from_status_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.status})"


class Block(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_made")
    blocked_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "blocked_user"], name="unique_community_block"),
        ]

    def __str__(self):
        return f"{self.user.username} blocked {self.blocked_user.username}"


class TradeRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("withdrawn", "Withdrawn"),
    ]
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trade_requests_sent")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trade_requests_received")
    # The specific card the RECIPIENT wants (from their public wishlist) that
    # this offer is about. Nullable -- a trade request can also just be a
    # general "saw your wishlist, let's talk" opener with no single card
    # pinned down yet.
    wanted_product = models.ForeignKey(
        'products.PokemonProduct', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="trade_requests",
    )
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["to_user", "status"], name="community_tr_to_status_idx"),
            models.Index(fields=["from_user"], name="community_tr_from_user_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.status})"


class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages_sent")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages_received")
    body = models.TextField(max_length=2000)
    trade_request = models.ForeignKey(
        TradeRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="community_msg_recip_read_idx"),
            models.Index(fields=["sender", "recipient", "created_at"], name="community_msg_thread_idx"),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}: {self.body[:40]}"


class Report(models.Model):
    REASON_CHOICES = [
        ("spam", "Spam / unsolicited advertising"),
        ("harassment", "Harassment or abuse"),
        ("scam", "Suspected scam / non-delivery"),
        ("inappropriate", "Inappropriate content"),
        ("other", "Other"),
    ]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_filed")
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_against")
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report: {self.reporter.username} -> {self.reported_user.username} ({self.reason})"
