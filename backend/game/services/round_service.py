
import secrets
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.utils import timezone

from game.models import GameRound


MIN_CRASH_MULTIPLIER = Decimal("1.0100")
MAX_CRASH_MULTIPLIER = Decimal("100.0000")
MULTIPLIER_PRECISION = Decimal("0.0001")





def generate_crash_multiplier():
    """
    Generate a virtual-game crash multiplier using a
    truncated exponential distribution.

    Small multipliers are more common than large ones.
    The result is stored before the round starts.
    """
    minimum = MIN_CRASH_MULTIPLIER
    maximum = MAX_CRASH_MULTIPLIER
    decay = Decimal("0.50")

    # Generate a high-resolution uniform random value in [0, 1).
    random_value = Decimal(secrets.randbelow(10**12)) / Decimal(10**12)

    width = maximum - minimum
    tail = (-decay * width).exp()

    # Inverse CDF of a truncated exponential distribution.
    remaining = Decimal("1") - random_value * (
        Decimal("1") - tail
    )

    multiplier = minimum - remaining.ln() / decay

    multiplier = min(max(multiplier, minimum), maximum)

    return multiplier.quantize(
        MULTIPLIER_PRECISION,
        rounding=ROUND_DOWN,
    )



@transaction.atomic
def create_waiting_round():
    latest = (
        GameRound.objects.select_for_update()
        .order_by("-round_number")
        .first()
    )

    next_number = 1 if latest is None else latest.round_number + 1

    return GameRound.objects.create(
        round_number=next_number,
        status=GameRound.Status.WAITING,
        scheduled_start_at=timezone.now(),
        final_multiplier=generate_crash_multiplier(),
    )



@transaction.atomic
def start_round(round_id):
    game_round = GameRound.objects.select_for_update().get(pk=round_id)

    if game_round.status != GameRound.Status.WAITING:
        raise ValueError("Only a waiting round can be started.")

    game_round.status = GameRound.Status.RUNNING
    game_round.started_at = timezone.now()
    game_round.save(update_fields=["status", "started_at", "updated_at"])

    return game_round



@transaction.atomic
def crash_round(round_id):
    game_round = GameRound.objects.select_for_update().get(pk=round_id)

    if game_round.status != GameRound.Status.RUNNING:
        raise ValueError("Only a running round can crash.")

    if game_round.final_multiplier is None:
        raise ValueError(
            "The round must have a final multiplier before it starts."
        )

    game_round.status = GameRound.Status.CRASHED
    game_round.crashed_at = timezone.now()
    game_round.save(
        update_fields=[
            "status",
            "crashed_at",
            "updated_at",
        ]
    )

    return game_round



@transaction.atomic
def complete_round(round_id):
    game_round = GameRound.objects.select_for_update().get(pk=round_id)

    if game_round.status != GameRound.Status.CRASHED:
        raise ValueError("Only a crashed round can be completed.")

    game_round.status = GameRound.Status.COMPLETED
    game_round.save(update_fields=["status", "updated_at"])

    return game_round


def get_display_multiplier(game_round):
    """
    Return the display multiplier based on elapsed server time.

    The display multiplier is illustrative. The final crash outcome
    is stored separately on the round.
    """
    if game_round.status == GameRound.Status.WAITING:
        return Decimal("0.00000")

    if game_round.status in (
        GameRound.Status.CRASHED,
        GameRound.Status.COMPLETED,
    ):
        return game_round.final_multiplier

    if game_round.status != GameRound.Status.RUNNING:
        raise ValueError("Unknown round status.")

    elapsed = Decimal(
        str(max((timezone.now() - game_round.started_at).total_seconds(), 0))
    )

   
    
    # Increase the display multiplier without exceeding the
    # predetermined crash point.
    multiplier = Decimal("1.0000") + (
        elapsed * Decimal("0.7000")
    )

    multiplier = multiplier.quantize(
        MULTIPLIER_PRECISION,
        rounding=ROUND_DOWN,
    )

    if game_round.final_multiplier is not None:
        return min(multiplier, game_round.final_multiplier)

    return multiplier


    return multiplier.quantize(
        MULTIPLIER_PRECISION,
        rounding=ROUND_DOWN,
    )


@transaction.atomic
def recover_interrupted_rounds():
    """
    Recover unfinished rounds after a controller restart.

    WAITING and RUNNING rounds are aborted.
    CRASHED rounds are completed without changing their outcome.
    """
    recovered = {
        "aborted": 0,
        "completed": 0,
    }

    unfinished_rounds = (
        GameRound.objects.select_for_update()
        .filter(
            status__in=[
                GameRound.Status.WAITING,
                GameRound.Status.RUNNING,
                GameRound.Status.CRASHED,
            ]
        )
        .order_by("round_number")
    )

    for game_round in unfinished_rounds:
        if game_round.status in (
            GameRound.Status.WAITING,
            GameRound.Status.RUNNING,
        ):
            game_round.status = GameRound.Status.ABORTED
            game_round.save(
                update_fields=["status", "updated_at"]
            )
            recovered["aborted"] += 1

        elif game_round.status == GameRound.Status.CRASHED:
            game_round.status = GameRound.Status.COMPLETED
            game_round.save(
                update_fields=["status", "updated_at"]
            )
            recovered["completed"] += 1

    return recovered


def seconds_until_crash(game_round):
    """
    Estimate the time in seconds until the predetermined
    crash multiplier is reached using the linear curve.
    """
    from decimal import ROUND_UP

    if game_round.final_multiplier is None:
        raise ValueError(
            "Round has no predetermined final multiplier."
        )

    elapsed_seconds = (
        game_round.final_multiplier - Decimal("1.0000")
    ) / Decimal("0.7000")

    return max(
        0,
        int(elapsed_seconds.to_integral_value(rounding=ROUND_UP)),
    )

