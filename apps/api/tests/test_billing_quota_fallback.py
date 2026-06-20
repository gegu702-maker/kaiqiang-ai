from app.services.billing import _get_plan_row, mark_order_paid_and_upgrade


class FakeResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = {}
        self.operation = "select"
        self.payload = None

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.operation == "select":
            return FakeResult(self.supabase.select(self.table_name, self.filters))
        if self.operation == "update":
            self.supabase.updates.setdefault(self.table_name, []).append(
                {"filters": dict(self.filters), "payload": self.payload}
            )
            return FakeResult([self.payload])
        if self.operation == "insert":
            self.supabase.inserts.setdefault(self.table_name, []).append(self.payload)
            return FakeResult([self.payload])
        return FakeResult()


class FakeSupabase:
    def __init__(self, *, orders=None, plans=None):
        self.orders = orders or {}
        self.plans = plans or {}
        self.updates = {}
        self.inserts = {}

    def table(self, table_name):
        return FakeQuery(self, table_name)

    def select(self, table_name, filters):
        if table_name == "plans":
            code = filters.get("code")
            return [self.plans[code]] if code in self.plans else []
        if table_name == "orders":
            order_id = filters.get("id")
            return [self.orders[order_id]] if order_id in self.orders else []
        return []


def make_order(plan):
    return {
        "id": f"order-{plan}",
        "user_id": f"user-{plan}",
        "plan": plan,
        "provider": "manual",
        "amount": 19900,
        "currency": "CNY",
        "billing_cycle": "monthly",
    }


def test_get_plan_row_uses_pricing_aligned_fallback_quotas():
    supabase = FakeSupabase()

    assert _get_plan_row(supabase, "plus")["monthly_quota"] == 1000
    assert _get_plan_row(supabase, "pro")["monthly_quota"] == 3000


def test_mark_order_paid_and_upgrade_assigns_plus_fallback_quota():
    order = make_order("plus")
    supabase = FakeSupabase(orders={order["id"]: order})

    mark_order_paid_and_upgrade(supabase, order_id=order["id"], provider_payment_id="manual-test")

    profile_update = supabase.updates["profiles"][0]["payload"]
    assert profile_update["plan"] == "plus"
    assert profile_update["monthly_quota"] == 1000


def test_mark_order_paid_and_upgrade_assigns_pro_fallback_quota():
    order = make_order("pro")
    supabase = FakeSupabase(orders={order["id"]: order})

    mark_order_paid_and_upgrade(supabase, order_id=order["id"], provider_payment_id="manual-test")

    profile_update = supabase.updates["profiles"][0]["payload"]
    assert profile_update["plan"] == "pro"
    assert profile_update["monthly_quota"] == 3000
