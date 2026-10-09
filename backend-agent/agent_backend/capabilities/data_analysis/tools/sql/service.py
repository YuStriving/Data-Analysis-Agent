from pydantic import BaseModel


class SqlPlan(BaseModel):
    sql: str
    reasoning: str


def build_read_only_sql(question: str) -> SqlPlan:
    return SqlPlan(
        sql="SELECT order_month, SUM(revenue) AS total_revenue FROM sales GROUP BY order_month ORDER BY order_month;",
        reasoning=f"Scaffold SQL for question: {question}",
    )

