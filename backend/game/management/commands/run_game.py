import math
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from game.models import GameEngineHeartbeat
from django.db import connection
from django.utils import timezone

from game.services.round_service import (
    complete_round,
    create_waiting_round,
    crash_round,
    get_display_multiplier,
    recover_interrupted_rounds,
    start_round,
)


LOCK_ID = 724190261



class RoundSettings:
    WAITING_SECONDS = 5
    RESULT_SECONDS = 2
    POLL_SECONDS = 0.05
    MULTIPLIER_SPEED = 0.5



class Command(BaseCommand):
    help = "Run the virtual game's server-side round controller."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one round and exit.",
        )

    def handle(self, *args, **options):
        acquired = False

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock(%s)",
                    [LOCK_ID],
                )
                acquired = cursor.fetchone()[0]

            if not acquired:
                self.stderr.write(
                    self.style.ERROR(
                        "Another game controller is already running."
                    )
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    "Virtual game round controller started."
                )
            )
            self.stdout.write("Press Ctrl+C to stop.")
            self.update_heartbeat(is_running=True)

            recovered = recover_interrupted_rounds()
            self.stdout.write(
                "Recovery complete: "
                f"{recovered['aborted']} round(s) aborted, "
                f"{recovered['completed']} crashed round(s) completed."
            )
            while True:
                self.update_heartbeat(is_running=True)
                self.run_round()

                if options["once"]:
                    break

        except KeyboardInterrupt:
            self.stdout.write("\nRound controller stopped.")

        finally:
            if acquired:
                try:
                    self.update_heartbeat(is_running=False)
                except Exception as exc:
                    self.stderr.write(
                        f"Could not update engine heartbeat: {exc}"
                    )
            if acquired and connection.connection is not None:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT pg_advisory_unlock(%s)",
                            [LOCK_ID],
                        )
                finally:
                    connection.close()


    def update_heartbeat(self, is_running=True):
        with transaction.atomic():
            heartbeat, _ = GameEngineHeartbeat.objects.get_or_create(
                id=1,
                defaults={
                    "last_heartbeat_at": timezone.now(),
                    "is_running": is_running,
                },
            )

            heartbeat.last_heartbeat_at = timezone.now()
            heartbeat.is_running = is_running
            heartbeat.save(
                update_fields=[
                    "last_heartbeat_at",
                    "is_running",
                    "updated_at",
                ]
            )

    def run_round(self):
        game_round = create_waiting_round()

        self.stdout.write(
            f"Round {game_round.round_number}: WAITING"
        )

        self.sleep_for(RoundSettings.WAITING_SECONDS)

        game_round = start_round(game_round.id)

        self.stdout.write(
            f"Round {game_round.round_number}: RUNNING "
            f"(predetermined crash point: "
            f"{game_round.final_multiplier}x)"
        )

       
        last_heartbeat = time.monotonic()

        while True:
            game_round.refresh_from_db()
            display_multiplier = get_display_multiplier(game_round)

            if display_multiplier >= game_round.final_multiplier:
                break

            if time.monotonic() - last_heartbeat >= 2:
                self.update_heartbeat(is_running=True)
                last_heartbeat = time.monotonic()

            self.sleep_for(RoundSettings.POLL_SECONDS)


        game_round = crash_round(game_round.id)

        self.stdout.write(
            f"Round {game_round.round_number}: CRASHED "
            f"at {game_round.final_multiplier}x"
        )

        self.sleep_for(RoundSettings.RESULT_SECONDS)

        game_round = complete_round(game_round.id)

        self.stdout.write(
            f"Round {game_round.round_number}: COMPLETED"
        )

    def sleep_for(self, seconds):
        deadline = timezone.now().timestamp() + seconds

        while True:
            remaining = deadline - timezone.now().timestamp()

            if remaining <= 0:
                return

            time.sleep(
                min(remaining, RoundSettings.POLL_SECONDS)
            )

def seconds_until_crash(game_round):
    """
    Return the estimated time to the stored crash point
    using the current linear multiplier curve.
    """
    if game_round.final_multiplier is None:
        raise ValueError(
            "Round has no predetermined final multiplier."
        )

    from decimal import ROUND_UP

    elapsed_seconds = (
        game_round.final_multiplier - Decimal("1.0000")
    ) / Decimal("0.7000")

    return max(
        0,
        int(elapsed_seconds.to_integral_value(rounding=ROUND_UP)),
    )

