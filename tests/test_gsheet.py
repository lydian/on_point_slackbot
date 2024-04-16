import pytest

from oncall_bot.gsheet import get_google_sheet


def test_gsheet():
    storage = get_google_sheet()
    conn = storage.engine.connect()
    result = conn.execute("select * from oncall_info")
    print(result.fetchall())
