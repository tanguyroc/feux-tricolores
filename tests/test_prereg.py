import datetime as dt


def test_archive_skips_intraday_values():
    """L'archive est en ajout seul : une valeur datée d'aujourd'hui avant la clôture de New York n'y entre pas."""
    from feux.prereg import _session_closed

    utc = dt.timezone.utc
    assert _session_closed("2026-11-09", dt.datetime(2026, 11, 9, 22, 17, tzinfo=utc))
    assert not _session_closed("2026-11-09", dt.datetime(2026, 11, 9, 7, 46, tzinfo=utc))
    assert _session_closed("2026-11-06", dt.datetime(2026, 11, 9, 7, 46, tzinfo=utc))
