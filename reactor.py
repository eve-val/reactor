import dataclasses
import datetime
import logging
import itertools
from typing import Any, DefaultDict, Dict, Iterable, List, Set, Tuple

from eve import market, services, world

DB_FILE_NAME = "/home/inazarenko/src/eve/data/db.sqlite"


REACTIONS = [
    46166,  # Caesarium Cadmide Reaction Formula
    46167,  # Carbon Polymers Reaction Formula
    46168,  # Ceramic Powder Reaction Formula
    46169,  # Crystallite Alloy Reaction Formula
    46170,  # Dysporite Reaction Formula
    46171,  # Fernite Alloy Reaction Formula
    46172,  # Ferrofluid Reaction Formula
    46173,  # Fluxed Condensates Reaction Formula
    46174,  # Hexite Reaction Formula
    46175,  # Hyperflurite Reaction Formula
    46176,  # Neo Mercurite Reaction Formula
    46177,  # Platinum Technite Reaction Formula
    46178,  # Rolled Tungsten Alloy Reaction Formula
    46179,  # Silicon Diborite Reaction Formula
    46180,  # Solerium Reaction Formula
    46181,  # Sulfuric Acid Reaction Formula
    46182,  # Titanium Chromide Reaction Formula
    46183,  # Vanadium Hafnite Reaction Formula
    46184,  # Prometium Reaction Formula
    46185,  # Thulium Hafnite Reaction Formula
    46186,  # Promethium Mercurite Reaction Formula
    46204,  # Titanium Carbide Reaction Formula
    46205,  # Crystalline Carbonide Reaction Formula
    46206,  # Fernite Carbide Reaction Formula
    46207,  # Tungsten Carbide Reaction Formula
    46208,  # Sylramic Fibers Reaction Formula
    46209,  # Fulleride Reaction Formula
    46210,  # Phenolic Composites Reaction Formula
    46211,  # Nanotransistors Reaction Formula
    46212,  # Hypersynaptic Fibers Reaction Formula
    46213,  # Ferrogel Reaction Formula
    46214,  # Fermionic Condensates Reaction Formula
    46215,  # Plasmonic Metamaterials Reaction Formula
    46216,  # Terahertz Metamaterials Reaction Formula
    46217,  # Photonic Metamaterials Reaction Formula
    46218,  # Nonlinear Metamaterials Reaction Formula
]


ItemPriceDict = Dict[world.ItemType, market.ItemPrice]
ItemPriceHistoryDict = Dict[world.ItemType, List[market.HistoricalItemPrice]]


@dataclasses.dataclass
class PricedFormula:
    name: str
    formula: world.Formula
    daily_volume_in_runs: float
    profit: float

    @property
    def profit_per_day(self):
        return 24.0 * 60 * 60 / self.formula.time * self.profit

    def print(self, w: world.World, ipc: market.ItemPriceCache):
        print(self.name)
        f = self.formula
        p = ipc.find_item_price(f.output.item_type)
        amt = p.low_price * f.output.quantity
        print(
            f"{amt:15,.0f} {f.output.quantity}x {f.output.item_type.name}; "
            f"volume (runs): {self.daily_volume_in_runs:,.0f}, "
            f"runtime {f.time}s"
        )

        for inp in f.inputs:
            p = ipc.find_item_price(inp.item_type)
            amt = -p.high_price * inp.quantity
            print(
                f"{amt:15,.0f} {inp.quantity}x {inp.item_type.name}; "
                f"volume (runs): {p.daily_trade_volume / inp.quantity:,.0f}"
            )
        print(
            f"= {self.profit:13,.0f} per run "
            f"({self.profit_per_day:,.0f} per day)"
        )


SALES_TAX_DISCOUNT = 0.95


def price_formula(
    ipc: ItemPriceDict, name: str, f: world.Formula
) -> PricedFormula:
    p = ipc[f.output.item_type]
    daily_volume_in_runs = p.daily_trade_volume / f.output.quantity
    amt = p.low_price * f.output.quantity
    total = amt * SALES_TAX_DISCOUNT

    for inp in f.inputs:
        p = ipc[inp.item_type]
        amt = -p.high_price * inp.quantity
        total += amt

    return PricedFormula(name, f, daily_volume_in_runs, total)


def fold_formula_with(
    f: world.Formula, to_fold: Dict[int, world.Formula]
) -> Tuple[str, world.Formula]:
    if not to_fold:
        return f.output.item_type.name, f
    new_items = []
    total_time = f.time
    for it in f.inputs:
        if it.item_type.id not in to_fold:
            new_items.append(it)
            continue
        sub_f = to_fold[it.item_type.id]
        multiplier = float(it.quantity) / sub_f.output.quantity
        total_time += multiplier * sub_f.time
        for s_it in sub_f.inputs:
            new_items.append(
                world.ItemQuantity(s_it.item_type, s_it.quantity * multiplier)
            )
    names = [it.output.item_type.name for it in to_fold.values()]
    sub_names = ", ".join(sorted(names))
    name = f"{f.output.item_type.name}[{sub_names}]"
    return name, world.Formula(f.blueprint, total_time, f.output, new_items)


def powerset(iterable):
    s = list(iterable)
    return itertools.chain.from_iterable(
        itertools.combinations(s, r) for r in range(len(s) + 1)
    )


def fold_formula(
    f: world.Formula, others: Dict[int, world.Formula]
) -> List[Tuple[str, world.Formula]]:
    foldable = [
        others[it.item_type.id] for it in f.inputs if it.item_type.id in others
    ]
    r = []
    for subset in powerset(foldable):
        to_fold = {it.output.item_type.id: it for it in subset}
        r.append(fold_formula_with(f, to_fold))
    return r


def print_industry_tree(w: world.World, padding: int, it: world.ItemType):
    bp = w.find_blueprint(it)
    if not bp:
        return
    f = w.find_formula(bp)

    print(" " * padding + f"{f.output.quantity}x {it.name} ({bp.group})")
    for inp in f.inputs:
        print(" " * padding + f"- {inp.quantity}x {inp.item_type.name}")

    for inp in f.inputs:
        print_industry_tree(w, padding + 2, inp.item_type)


def fold_all_formulas(
    formulas: List[world.Formula],
) -> List[Tuple[str, world.Formula]]:
    formulas_by_output = {f.output.item_type.id: f for f in formulas}
    r = []
    for f in formulas:
        r.extend(fold_formula(f, formulas_by_output))
    return r


def get_all_items(formulas: List[world.Formula]) -> Set[world.ItemType]:
    r: Set[world.ItemType] = set()
    for f in formulas:
        r.add(f.output.item_type)
        r.update(it.item_type for it in f.inputs)
    return r


def get_all_prices(
    ipc: market.ItemPriceCache, items: Iterable[world.ItemType]
) -> ItemPriceDict:
    return {it: ipc.find_item_price(it) for it in items}


def get_all_price_histories(
    ipc: market.ItemPriceCache, items: Iterable[world.ItemType]
) -> ItemPriceHistoryDict:
    return {it: ipc.get_price_history(it) for it in items}


def get_price_snapshot(
    hist: ItemPriceHistoryDict, d: datetime.date
) -> ItemPriceDict:
    r = {}
    last_updated = datetime.datetime(d.year, d.month, d.day)
    time_radius = datetime.timedelta(days=2)
    min_date = d - time_radius
    max_date = d + time_radius
    for it, prices in hist.items():
        price_slice = [
            p for p in prices if p.date >= min_date and p.date <= max_date
        ]
        lo = 0.95 * max(p.lowest for p in price_slice)
        hi = 1.05 * min(p.highest for p in price_slice)
        vol = sum(p.volume for p in price_slice) / len(price_slice)
        r[it] = market.ItemPrice(it.id, last_updated, vol, lo, hi)
    return r


def get_common_dates(prices: ItemPriceHistoryDict) -> List[datetime.date]:
    r = None
    for price_list in prices.values():
        if r is None:
            r = set(p.date for p in price_list)
        else:
            r = r.intersection(p.date for p in price_list)
    if r is None:
        return []
    return sorted(r)


def profit_key(xs: List[float]) -> Any:
    return (sum(bool(x > 100000) for x in xs), sum(xs))


def history():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    formulas = [w.find_formula(w.find_item_type(id)) for id in REACTIONS]
    prices = get_all_price_histories(ipc, get_all_items(formulas))
    all_formulas = fold_all_formulas(formulas)
    dates = get_common_dates(prices)
    results = {name: [] for name, _ in all_formulas}
    for d in dates:
        price_slice = get_price_snapshot(prices, d)
        for name, f in all_formulas:
            pf = price_formula(price_slice, name, f)
            results[name].append(pf.profit_per_day)
    results = [
        (name, profits)
        for name, profits in results.items()
    ]
    results.sort(key=lambda x: profit_key(x[1]), reverse=True)
    seen_products = set()
    for name, r in results:
        product = name.split("[")[0]
        if product in seen_products:
            continue
        seen_products.add(product)
        print(name + ", " + ", ".join(f"{x:.0f}" for x in r))


def reactor():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    formulas = [w.find_formula(w.find_item_type(id)) for id in REACTIONS]
    prices = get_all_prices(ipc, get_all_items(formulas))
    formulas_by_output = {f.output.item_type.id: f for f in formulas}
    priced = []
    for f in formulas:
        folded = [
            price_formula(prices, name, f)
            for name, f in fold_formula(f, formulas_by_output)
        ]
        folded.sort(key=lambda p: p.profit_per_day, reverse=True)
        priced.append(folded[0])
    priced.sort(key=lambda p: p.profit_per_day, reverse=True)
    for p in priced:
        p.print(w, ipc)
        print()


def shopper():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    f = w.find_formula(w.find_item_type(46210))
    qty = 500
    for i in f.inputs:
        p = ipc.get_price_history(i.item_type)
        p = p[-15:]
        print(f"{i.item_type.name} x{i.quantity * qty}")
        print("  v:" + " ".join(f"{d.volume:8,.0f}" for d in p))
        print("=" * (9 * 15 + 3))
        print("  h:" + " ".join(f"{d.highest:8,.0f}" for d in p))
        print("  a:" + " ".join(f"{d.average:8,.0f}" for d in p))
        print("  l:" + " ".join(f"{d.lowest:8,.0f}" for d in p))
        print()


if __name__ == "__main__":
    reactor()
