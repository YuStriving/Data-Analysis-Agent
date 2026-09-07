def build_line_chart(title: str) -> dict:
    return {
        "title": {"text": title},
        "xAxis": {"type": "category", "data": ["Jan", "Feb", "Mar"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "data": [120, 132, 101]}],
    }

