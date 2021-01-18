import dataclasses
import datetime
import logging
import itertools
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

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

# Local materials:
# =========================================
# Neodymium (64)
# Thulium (64)
# Caesium (32)
# Chromium (16)
# Cadmium (16)
# Tungsten/Titanium/Scandium (8)
# Evaporite/Silicates/Hydrocarbons (4)
# When NSH moves out:
# Scandium
# Platinum
# Promethium

ItemPriceSource = Callable[[world.ItemType], market.ItemPrice]
ItemPriceHistoryDict = Dict[world.ItemType, List[market.HistoricalItemPrice]]

SYSTEM_COST_FACTOR = 0.02
SHIPMENT_COST_PER_M3 = 200


@dataclasses.dataclass
class PricedFormula:
    name: str
    formula: world.Formula
    daily_volume_in_runs: float
    profit: float
    input_cost: float
    job_cost: float

    @property
    def runs_per_day(self):
        return 24.0 * 60 * 60 / self.formula.time

    @property
    def profit_per_day(self):
        return self.runs_per_day * self.profit

    def print(self, w: world.World, ipc: market.ItemPriceCache):
        print(
            f"{self.name}  ---  {self.profit_per_day:,.0f}/day at "
            f"{self.profit / self.input_cost * 100:.1f}%"
        )
        f = self.formula
        p = ipc.find_item_price(f.output.item_type)
        amt = p.low_price * f.output.quantity
        print(
            f"{amt:15,.0f} {f.output.quantity}x {f.output.item_type.name}; "
            f"volume (runs): {self.daily_volume_in_runs:,.0f}, "
            f"runtime {f.time}s"
        )

        input_amt = 0.0
        input_m3 = 0.0
        for inp in f.inputs:
            p = ipc.find_item_price(inp.item_type)
            amt = -p.high_price * inp.quantity
            input_amt += amt
            input_m3 += inp.item_type.volume_m3 * inp.quantity
            print(
                f"{amt:15,.0f} {inp.quantity}x {inp.item_type.name}; "
                f"volume (runs): {p.daily_trade_volume / inp.quantity:,.0f}"
            )
        print(f"{-self.job_cost:15,.0f} job cost")
        output_m3 = f.output.quantity * f.output.item_type.volume_m3
        ship_cost = -(input_m3 + output_m3) * SHIPMENT_COST_PER_M3
        print(
            f"{ship_cost:15,.0f} shipment cost "
            f"for {input_m3+output_m3:,.0f} m3"
        )
        input_m3 *= self.runs_per_day
        output_m3 *= self.runs_per_day
        print(
            f"= {self.profit:13,.0f} per run; "
            f"per day ISK: {self.profit_per_day:,.0f}; "
            f"m3: import {input_m3:,.0f}, export {output_m3:,.0f}"
        )


SALES_TAX_DISCOUNT = 0.97


def price_formula(
    ips: ItemPriceSource, name: str, f: world.Formula, me=1.0
) -> PricedFormula:
    p = ips(f.output.item_type)
    daily_volume_in_runs = p.daily_trade_volume / f.output.quantity
    amt = p.low_price * f.output.quantity
    total = amt * SALES_TAX_DISCOUNT
    total_m3 = f.output.quantity * f.output.item_type.volume_m3
    input_amt = 0.0
    for inp in f.inputs:
        p = ips(inp.item_type)
        qty = max(1.0, me * inp.quantity)
        input_amt += p.high_price * qty
        total_m3 += inp.quantity * inp.item_type.volume_m3
    job_cost = input_amt * SYSTEM_COST_FACTOR
    for i in f.intermediates:
        p = ips(i.item_type)
        job_cost += SYSTEM_COST_FACTOR * (p.high_price * i.quantity)
    total -= input_amt
    total -= total_m3 * SHIPMENT_COST_PER_M3
    total -= job_cost

    return PricedFormula(
        name, f, daily_volume_in_runs, total, input_amt, job_cost
    )


def fold_formula_with(
    f: world.Formula, to_fold: Dict[int, world.Formula]
) -> Tuple[str, world.Formula]:
    if not to_fold:
        return f.output.item_type.name, f
    new_items: List[world.ItemQuantity] = []
    intermediates: List[world.ItemQuantity] = []
    total_time = f.time
    for it in f.inputs:
        if it.item_type.id not in to_fold:
            new_items.append(it)
            continue
        sub_f = to_fold[it.item_type.id]
        intermediates.append(sub_f.output)
        multiplier = float(it.quantity) / sub_f.output.quantity
        total_time += multiplier * sub_f.time
        for s_it in sub_f.inputs:
            new_items.append(
                world.ItemQuantity(s_it.item_type, s_it.quantity * multiplier)
            )
    names = [it.output.item_type.name for it in to_fold.values()]
    sub_names = "/".join(sorted(names))
    name = f"{f.output.item_type.name}[{sub_names}]"
    return name, world.Formula(
        f.blueprint,
        total_time,
        f.output,
        new_items,
        intermediates=intermediates,
    )


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


def get_all_price_histories(
    ipc: market.ItemPriceCache, items: Iterable[world.ItemType]
) -> ItemPriceHistoryDict:
    return {it: ipc.get_price_history(it) for it in items}


def get_price_snapshot(
    hist: ItemPriceHistoryDict, d: datetime.date
) -> ItemPriceSource:
    r = {}
    last_updated = datetime.datetime(d.year, d.month, d.day)
    time_radius = datetime.timedelta(days=2)
    min_date = d - time_radius
    max_date = d + time_radius
    for it, prices in hist.items():
        lo = 0.95 * max(
            p.lowest for p in prices if p.date >= d and p.date <= max_date
        )
        hi = 1.05 * min(
            p.highest for p in prices if p.date >= min_date and p.date <= d
        )
        price_slice = [
            p for p in prices if p.date >= min_date and p.date <= max_date
        ]
        vol = sum(p.volume for p in price_slice) / len(price_slice)
        r[it] = market.ItemPrice(it.id, last_updated, vol, lo, hi)
    return lambda it: r[it]


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
    results = [(name, profits) for name, profits in results.items()]
    results.sort(key=lambda x: profit_key(x[1]), reverse=True)
    seen_products = set()
    for name, r in results:
        product = name.split("[")[0]
        # if product in seen_products:
        #     continue
        seen_products.add(product)
        print(name + ", " + ", ".join(f"{x:.0f}" for x in r))


def reactor():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    formulas = [w.find_formula(w.find_item_type(id)) for id in REACTIONS]
    formulas_by_output = {f.output.item_type.id: f for f in formulas}
    priced = []
    for f in formulas:
        folded = [
            price_formula(lambda it: ipc.find_item_price(it), name, f)
            for name, f in fold_formula(f, formulas_by_output)
        ]
        # folded.sort(key=lambda p: p.profit_per_day, reverse=True)
        # priced.append(folded[0])
        priced.extend(folded)
    priced.sort(key=lambda p: (p.profit / p.input_cost), reverse=True)
    for p in priced:
        p.print(w, ipc)
        print()


def get_formula_for_item_name(w: world.World, item: str) -> world.Formula:
    return w.find_formula(w.find_blueprint(w.find_item_type_by_name(item)))


def name_to_formula(w: world.World, name: str) -> world.Formula:
    main_name = name.split("[")[0].strip()
    main_formula = get_formula_for_item_name(w, main_name)
    if main_name == name:
        return main_formula
    mats_names = name[len(main_name) :].strip("[]").split("/")
    mats = [get_formula_for_item_name(w, m) for m in mats_names]
    return fold_formula_with(
        main_formula, {m.output.item_type.id: m for m in mats}
    )[1]


def print_price_history(ph: List[market.HistoricalItemPrice]):
    ph = ph[-15:]
    if ph[-1].volume > 1e6:
        print("  v:" + " ".join(f"{d.volume/1000:8,.0f}K" for d in ph))
    else:
        print("  v:" + " ".join(f"{d.volume:9,.0f}" for d in ph))
    print("=" * (10 * 15 + 3))
    print("  h:" + " ".join(f"{d.highest:9,.0f}" for d in ph))
    print("  a:" + " ".join(f"{d.average:9,.0f}" for d in ph))
    print("  l:" + " ".join(f"{d.lowest:9,.0f}" for d in ph))


def shopper():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    # name = "Sylramic Fibers[Ceramic Powder/Hexite]"
    name = "Sylramic Fibers[Ceramic Powder]"
    # name = "Phenolic Composites"
    f = name_to_formula(w, name)

    print(f.output.item_type.name)
    print_price_history(ipc.get_price_history(f.output.item_type))
    print()

    qty = 344
    total = 0.0
    total_m3 = 0.0
    for i in f.inputs:
        p = ipc.find_item_price(i.item_type)
        amt = qty * i.quantity * p.high_price
        total += amt
        total_m3 += qty * i.quantity * i.item_type.volume_m3
        print(
            f"{i.item_type.name} x{i.quantity * qty} "
            f"buy @{p.high_price:,.0f} {amt:,.0f}"
        )
        print_price_history(ipc.get_price_history(i.item_type))
        print()
    print(f"Total: {total:,.0f} ISK, {total_m3:,.0f} m3")
    print("Multibuy:")
    for i in f.inputs:
        print(f"{qty * i.quantity:.0f}x {i.item_type.name}")
    print()


def test():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)
    # Direct list of items
    items = [
        # Weapons
        "Rapid Light Missile Launcher II",
        "720mm Howitzer Artillery II",
        "Heavy Missile Launcher II",
        "Heavy Assault Missile Launcher II",
        "Mega Pulse Laser II",
        "425mm AutoCannon II",
        "Small Focused Beam Laser II",
        # Drones
        "Warrior II",
        "Acolyte II",
        "Hornet II",
        "Hobgoblin II",
        "Hammerhead II",
        "Infiltrator II",
        "Valkyrie II",
        "Ogre II",
        # Tank
        "Large Shield Extender II",
        "Medium Shield Extender II",
        "Multispectrum Shield Hardener II",
        "Large Shield Booster II",
        "Nanofiber Internal Structure II",
        "Damage Control II",
        "Assault Damage Control II",
        "Medium Armor Repairer II",
        "Multispectrum Energized Membrane II",
        "Shield Power Relay II",
        # Eng. and misc
        "Co-Processor II",
        "Warp Disruptor II",
        "Stasis Webifier II",
        "Warp Scrambler II",
        "Medium Capacitor Booster II",
        # Damage mods
        "Drone Damage Amplifier II",
        "Heat Sink II",
        "Gyrostabilizer II",
        "Ballistic Control System II",
        "Magnetic Field Stabilizer II",
        "Tracking Enhancer II",
        # Rigs
        "Medium Core Defense Field Purger I",
        "Medium Core Defense Field Purger II",
        "Medium Core Defense Field Extender II",
        "Medium EM Shield Reinforcer II",
        "Medium Thermal Shield Reinforcer II",
        "Medium Hydraulic Bay Thrusters II",
        "Medium Rocket Fuel Cache Partition II",
        "Medium Energy Locus Coordinator II",
        "Medium Hyperspatial Velocity Optimizer II",
        "Small Energy Locus Coordinator II",
        # Fuel
        "Helium Fuel Block",
        "Hydrogen Fuel Block",
        "Nitrogen Fuel Block",
        "Oxygen Fuel Block",
    ]

    # Formulas for items assuming T2 BP exists
    fs = [get_formula_for_item_name(w, item) for item in items]
    # All formulas that use a material
    # mat = w.find_item_type_by_name("Sylramic Fibers")
    # fs = w.find_material_uses(mat)
    # fs = [f for f in fs if not f.output.item_type.is_capital]
    # Invention cost (not really correct)
    # fs = [
    #     w.find_invention_formula(w.find_blueprint(w.find_item_type_by_name(n)))
    #     for n in items
    # ]
    # fs = [f for f in fs if f]
    priced = [
        price_formula(
            lambda it: ipc.find_item_price(it), f.output.item_type.name, f
        )
        for f in fs
    ]
    priced.sort(key=lambda f: (f.profit / f.input_cost), reverse=True)
    for p in priced:
        p.print(w, ipc)


if __name__ == "__main__":
    shopper()
