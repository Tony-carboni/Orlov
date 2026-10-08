"""The profit calculation. Pure functions; no database access."""

from dataclasses import dataclass, field

from .. import app_settings, constants


@dataclass
class TaxRates:
    sales_tax: float  # fraction, e.g. 0.0337
    broker_fee: float  # fraction
    source: str = ""


def tax_rates(market, settings) -> TaxRates:
    """Sales tax and broker fee for a member at a market location."""
    if settings and settings.manual_sales_tax is not None:
        sales = float(settings.manual_sales_tax) / 100.0
        src = "manual"
    else:
        base = float(market.sales_tax_base) / 100.0 if market else 0.075
        acc = settings.accounting if settings else 0
        sales = base * (1.0 - app_settings.SHIPYARD_ACCOUNTING_REDUCTION_PER_LEVEL * acc)
        src = "skills"
    if settings and settings.manual_broker_fee is not None:
        broker = float(settings.manual_broker_fee) / 100.0
    else:
        base = float(market.broker_fee_base) / 100.0 if market else 0.03
        if market is None or market.is_npc_station:
            br = settings.broker_relations if settings else 0
            broker = base - app_settings.SHIPYARD_BROKER_RELATIONS_REDUCTION_PER_LEVEL * br
            if settings is not None and market is not None:
                # standings with the station's owners (unmodified, as the game uses them)
                broker -= app_settings.SHIPYARD_BROKER_FACTION_STANDING_PER_POINT * settings.standing_with(market.owner_faction_id)
                broker -= app_settings.SHIPYARD_BROKER_CORP_STANDING_PER_POINT * settings.standing_with(market.owner_corporation_id)
            broker = max(0.0, broker)
        else:
            broker = base
    return TaxRates(sales_tax=sales, broker_fee=broker, source=src)


@dataclass
class MaterialLine:
    type_id: int
    name: str
    quantity: float
    unit_price: float | None
    volume: float = 0.0

    @property
    def cost(self) -> float:
        return (self.unit_price or 0.0) * self.quantity

    @property
    def total_volume(self) -> float:
        return self.volume * self.quantity


@dataclass
class ShipEconomics:
    sell_price: float | None
    materials: list[MaterialLine] = field(default_factory=list)
    job_cost: float = 0.0
    bpc_cost: float = 0.0
    bpc_source: str = "manual"  # free | lp | manual | public | own (the member's own typed price)
    bpc_excluded: bool = False  # True: no blueprint source, net profit is without the blueprint
    bpc_markup: float = 0.0  # fraction added on top of the LP-store cost (corp policy)
    tag_cost: float = 0.0
    sales_tax_rate: float = 0.0
    broker_fee_rate: float = 0.0
    avg_daily_volume: float = 0.0
    sell_volume_on_market: float = 0.0
    time_seconds: int = 0
    missing_prices: int = 0

    @property
    def material_cost(self) -> float:
        return sum(m.cost for m in self.materials)

    @property
    def material_volume(self) -> float:
        return sum(m.total_volume for m in self.materials)

    @property
    def sales_tax(self) -> float:
        return (self.sell_price or 0.0) * self.sales_tax_rate

    @property
    def broker_fee(self) -> float:
        return (self.sell_price or 0.0) * self.broker_fee_rate

    @property
    def fees(self) -> float:
        return self.sales_tax + self.broker_fee

    @property
    def total_cost(self) -> float:
        return self.material_cost + self.job_cost + self.bpc_cost + self.tag_cost + self.sales_tax + self.broker_fee

    @property
    def net_profit(self) -> float | None:
        if self.sell_price is None:
            return None
        return self.sell_price - self.total_cost

    @property
    def margin(self) -> float | None:
        if not self.sell_price:
            return None
        return (self.net_profit or 0.0) / self.sell_price

    @property
    def market_depth_days(self) -> float | None:
        """Units on sell orders divided by average daily sales."""
        if self.avg_daily_volume <= 0:
            return None
        return self.sell_volume_on_market / self.avg_daily_volume

    @property
    def complete(self) -> bool:
        return self.sell_price is not None and self.missing_prices == 0 and bool(self.materials)


def corp_markup(markup=None) -> float:
    """The markup on an LP-store copy: a member's own rate, else the corp's default."""
    return float(markup) if markup is not None else float(app_settings.SHIPYARD_CORP_BPC_MARKUP)


def blueprint_cost(config, use_lp: bool, category: str | None = None, hull_size: str | None = None, markup=None, name=None, own_price=None) -> tuple[float, str]:
    """Blueprint price per run and where it came from, following the blueprint policy.

    Without a category (older callers, tests) only the LP/manual choice applies.
    `markup` overrides the corp's default rate (a fraction; 0 = at cost).
    `name` lets the per-ship exceptions apply (constants.BPC_POLICY_BY_NAME).
    `own_price` is the member's own typed price for the copy: it wins over everything.
    """
    if own_price is not None:
        return float(own_price), "own"
    policy = constants.bpc_policy(category, hull_size, name)
    if policy == constants.BPC_FREE:
        return 0.0, "free"
    if policy == constants.BPC_PUBLIC:
        return 0.0, "public"
    if config is None:
        return 0.0, "none"
    if use_lp and config.has_lp_offer:
        price = config.lp_bpc_price_per_run()
        if price is not None:
            if policy == constants.BPC_CORP:
                price *= 1.0 + corp_markup(markup)
            return float(price), "lp"
    return float(config.bpc_price_isk or 0), "manual"


def economics(
    *,
    sell_price,
    material_rows,
    prices,
    names,
    volumes,
    job_cost,
    config,
    use_lp,
    rates: TaxRates,
    avg_daily_volume=0.0,
    sell_volume_on_market=0.0,
    time_seconds=0,
    tag_unit_price=None,
    category=None,
    hull_size=None,
    markup=None,
    name=None,
    own_price=None,
) -> ShipEconomics:
    """Assemble the economics of one ship from snapshot data.

    material_rows: [{type_id, quantity}], prices: {type_id: unit price or None},
    names: {type_id: name}, volumes: {type_id: m³}, tag_unit_price: lowest sell of
    the config's tag type (None when unknown, which marks the ship incomplete).
    """
    lines = []
    missing = 0
    for row in material_rows:
        tid = int(row["type_id"])
        price = prices.get(tid)
        if price is None:
            missing += 1
        lines.append(MaterialLine(
            type_id=tid,
            name=names.get(tid, f"Type {tid}"),
            quantity=float(row["quantity"]),
            unit_price=price,
            volume=float(volumes.get(tid, 0.0)),
        ))
    bpc, src = blueprint_cost(config, use_lp, category, hull_size, markup, name, own_price)
    applied_markup = 0.0
    if src in ("public", "own"):
        # no blueprint source, or the member's own quote for the whole copy:
        # the tags that come with the LP offer are left out as well
        tag_cost, tag_missing = 0.0, False
    else:
        tag_cost, tag_missing = config.tag_cost(tag_unit_price) if config else (0.0, False)
        if src == "lp" and constants.bpc_policy(category, hull_size, name) == constants.BPC_CORP:
            applied_markup = corp_markup(markup)
            tag_cost *= 1.0 + applied_markup
    if tag_missing:
        missing += 1
    return ShipEconomics(
        sell_price=sell_price,
        materials=lines,
        job_cost=float(job_cost or 0),
        bpc_cost=bpc,
        bpc_source=src,
        bpc_excluded=(src == "public"),
        bpc_markup=applied_markup,
        tag_cost=tag_cost,
        sales_tax_rate=rates.sales_tax,
        broker_fee_rate=rates.broker_fee,
        avg_daily_volume=float(avg_daily_volume or 0),
        sell_volume_on_market=float(sell_volume_on_market or 0),
        time_seconds=int(time_seconds or 0),
        missing_prices=missing,
    )
