"""Words for a shop's report: the email, its table, and the values of the WhatsApp template."""

from html import escape
from typing import List, Tuple

PERIOD_WORDS = {"daily": "daily", "weekly": "weekly", "monthly": "monthly", "yearly": "yearly"}


def _inr(amount) -> str:
    """Indian digit grouping, with the sign in front: 1234567.5 -> -12,34,567.50 for a loss."""
    value = float(amount or 0)
    sign = "-" if value < 0 else ""
    whole, paise = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}₹{whole}" + ("" if paise == "00" else f".{paise}")


def _rows(report: dict) -> List[Tuple[str, str]]:
    return [
        ("Bookings completed", str(report.get("bookings", 0))),
        ("Customers paid", _inr(report.get("gross"))),
        ("  Paid in cash", _inr(report.get("cash"))),
        ("  Paid online", _inr(report.get("online"))),
        ("Platform commission", _inr(report.get("commission"))),
        ("GST on commission", _inr(report.get("gst"))),
        ("You earned from bookings", _inr(report.get("earned"))),
        ("Other income", _inr(report.get("other_income"))),
        ("Expenses", _inr(report.get("expenses"))),
        ("PROFIT" if float(report.get("profit") or 0) >= 0 else "LOSS", _inr(report.get("profit"))),
        ("Tips (not in profit)", _inr(report.get("tips"))),
    ]


def _trend(report: dict) -> str:
    change = report.get("profit_change_percent")
    if change is None:
        return ""
    return f"Profit is {'up' if change >= 0 else 'down'} {abs(change):g}% on the period before."


def subject(report: dict, shop_name: str) -> str:
    return f"{shop_name or 'Your business'}: {PERIOD_WORDS.get(report.get('period'), '')} report, {report.get('label')}"


def text_body(report: dict, shop_name: str) -> str:
    lines = [f"{shop_name}: report for {report.get('label')}", ""]
    lines += [f"{label}: {value}" for label, value in _rows(report)]
    if _trend(report):
        lines += ["", _trend(report)]
    if report.get("expenses_by_category"):
        lines += ["", "Where the money went:"]
        lines += [f"  {_category(r['category'])}: {_inr(r['amount'])}" for r in report["expenses_by_category"]]
    lines += [
        "",
        report.get("note") or "",
        "",
        "The attached file has the full figures, for your records or your accountant.",
    ]
    lines += [
        "",
        "This is an automatic message from AlakhService; replies are not read.",
        "You can change these reports in the app.",
    ]
    return "\n".join(lines) + "\n"


def _category(code: str) -> str:
    return code.replace("_", " ").capitalize()


def html_body(report: dict, shop_name: str) -> str:
    rows = "".join(
        f"<tr><td style='padding:6px 12px 6px 0'>{'<b>' + escape(k) + '</b>' if k in ('PROFIT', 'LOSS') else escape(k)}</td>"
        f"<td style='padding:6px 0;text-align:right'>{'<b>' + escape(v) + '</b>' if k in ('PROFIT', 'LOSS') else escape(v)}</td></tr>"
        for k, v in _rows(report)
    )
    trend = f"<p>{escape(_trend(report))}</p>" if _trend(report) else ""
    spent = ""
    if report.get("expenses_by_category"):
        items = "".join(
            f"<li>{escape(_category(r['category']))}: {escape(_inr(r['amount']))}</li>"
            for r in report["expenses_by_category"]
        )
        spent = f"<p><b>Where the money went</b></p><ul>{items}</ul>"
    return (
        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222;max-width:480px'>"
        f"<h2 style='font-size:18px'>{escape(shop_name)}: {escape(str(report.get('label')))}</h2>"
        f"<table style='border-collapse:collapse;width:100%'>{rows}</table>{trend}{spent}"
        f"<p style='color:#666;font-size:12px'>{escape(report.get('note') or '')}</p>"
        "<p style='color:#666;font-size:12px'>The attached file has the full figures. This is an automatic message "
        "from AlakhService; replies are not read. You can change these reports in the app.</p></div>"
    )


def whatsapp_values(report: dict, shop_name: str) -> List[str]:
    """{{1}} business, {{2}} which report, {{3}} bookings, {{4}} earned, {{5}} expenses, {{6}} profit or loss."""
    earned = float(report.get("earned") or 0) + float(report.get("other_income") or 0)
    return [
        shop_name or "your business",
        str(report.get("label")),
        str(report.get("bookings", 0)),
        _inr(earned),
        _inr(report.get("expenses")),
        _inr(report.get("profit")),
    ]
