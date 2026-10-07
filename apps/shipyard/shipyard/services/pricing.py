"""The profit calculation. Pure functions; no database access."""

from dataclasses import dataclass, field

from .. import app_settings


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
            broker = max(0.0, base - app_settings.SHIPYARD_BROKER_RELATIONS_REDUCTION_PER_LEVEL * br)
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
    bpc_source: str = "manual"
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


def blueprint_cost(config, use_lp: bool) -> tuple[float, str]:
    """Blueprint price per run and where it came from."""
    if config is None:
        return 0.0, "none"
    if use_lp and config.has_lp_offer:
        price = config.lp_bpc_price_per_run()
        if price is not None:
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
    bpc, src = blueprint_cost(config, use_lp)
    tag_cost, tag_missing = config.tag_cost(tag_unit_price) if config else (0.0, False)
    if tag_missing:
        missing += 1
    return ShipEconomics(
        sell_price=sell_price,
        materials=lines,
        job_cost=float(job_cost or 0),
        bpc_cost=bpc,
        bpc_source=src,
        tag_cost=tag_cost,
        sales_tax_rate=rates.sales_tax,
        broker_fee_rate=rates.broker_fee,
        avg_daily_volume=float(avg_daily_volume or 0),
        sell_volume_on_market=float(sell_volume_on_market or 0),
        time_seconds=int(time_seconds or 0),
        missing_prices=missing,
    )
