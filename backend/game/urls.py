
from django.urls import path

from game.views import (
    CashOutBetView,
    CurrentBetsView,
    CurrentGameRoundView,
    GameEngineHealthView,
    JackpotListView,
    PlaceBetView,
)

app_name = "game"

urlpatterns = [
    path(
        "rounds/current/",
        CurrentGameRoundView.as_view(),
        name="current-round",
    ),
    path(
        "engine/health/",
        GameEngineHealthView.as_view(),
        name="engine-health",
    ),
    path("bets/", PlaceBetView.as_view(), name="place-bet"),
    path("bets/cash-out/", CashOutBetView.as_view(), name="cash-out-bet"),
    path("bets/current/", CurrentBetsView.as_view(), name="current-bets"),
    path("jackpots/", JackpotListView.as_view(), name="jackpot-list"),
]
