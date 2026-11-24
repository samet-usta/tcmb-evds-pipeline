"""Unit tests for evds_compare (no database)."""

from src.simulation import evds_compare


def patch_db(monkeypatch, dev_count, ref_count, dev_minus_ref, ref_minus_dev):
    """Replace the four database helpers with fixed values."""

    def fake_columns(conn, schema, table):
        return ["series_code"]

    def fake_count_rows(conn, schema, table):
        if schema == evds_compare.DEV_SCHEMA:
            return dev_count
        return ref_count

    def fake_count_except(conn, table, columns, schema_a, schema_b):
        if schema_a == evds_compare.DEV_SCHEMA:
            return dev_minus_ref
        return ref_minus_dev

    monkeypatch.setattr(evds_compare, "get_compare_columns", fake_columns)
    monkeypatch.setattr(evds_compare, "count_rows", fake_count_rows)
    monkeypatch.setattr(evds_compare, "count_except", fake_count_except)


class FakeConn:
    def close(self):
        pass


def test_compare_table_equal_is_ok(monkeypatch):
    patch_db(monkeypatch, 63, 63, 0, 0)
    result = evds_compare.compare_table(None, "fct_rates")
    assert result["ok"] is True


def test_compare_table_row_count_diff_is_not_ok(monkeypatch):
    patch_db(monkeypatch, 63, 62, 0, 0)
    result = evds_compare.compare_table(None, "fct_rates")
    assert result["ok"] is False


def test_compare_table_except_diff_is_not_ok(monkeypatch):
    patch_db(monkeypatch, 63, 63, 1, 0)
    result = evds_compare.compare_table(None, "fct_rates")
    assert result["ok"] is False
    assert result["dev_minus_ref"] == 1


def test_compare_marts_follows_table_order(monkeypatch):
    patch_db(monkeypatch, 1, 1, 0, 0)
    results = evds_compare.compare_marts(None)
    names = []
    for result in results:
        names.append(result["table"])
    assert names == ["fct_rates", "fct_volumes", "fct_rates_daily"]


def test_main_exit_code(monkeypatch):
    monkeypatch.setattr(evds_compare, "get_connection", lambda: FakeConn())

    ok_results = [{"table": "t", "dev_count": 1, "ref_count": 1,
                   "dev_minus_ref": 0, "ref_minus_dev": 0, "ok": True}]
    diff_results = [{"table": "t", "dev_count": 1, "ref_count": 1,
                     "dev_minus_ref": 1, "ref_minus_dev": 1, "ok": False}]

    monkeypatch.setattr(evds_compare, "compare_marts", lambda conn: ok_results)
    assert evds_compare.main() == 0

    monkeypatch.setattr(evds_compare, "compare_marts", lambda conn: diff_results)
    assert evds_compare.main() == 1
