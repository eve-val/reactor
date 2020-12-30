import dataclasses
import logging
import itertools
from typing import Dict, List, Optional

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


@dataclasses.dataclass
class PricedFormula:
    formula: world.Formula
    daily_volume_in_runs: float
    profit: float

    @property
    def profit_per_day(self):
        return 24.0 * 60 * 60 / self.formula.time * self.profit

    def print(self, w: world.World, ipc: market.ItemPriceCache):
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
    ipc: market.ItemPriceCache, f: world.Formula, verbose: bool = False
) -> PricedFormula:
    p = ipc.find_item_price(f.output.item_type)
    daily_volume_in_runs = p.daily_trade_volume / f.output.quantity
    amt = p.low_price * f.output.quantity
    total = amt * SALES_TAX_DISCOUNT

    for inp in f.inputs:
        p = ipc.find_item_price(inp.item_type)
        amt = -p.high_price * inp.quantity
        total += amt

    return PricedFormula(f, daily_volume_in_runs, total)


def fold_formula_with(
    f: world.Formula, to_fold: Dict[int, world.Formula]
) -> world.Formula:
    if not to_fold:
        return f
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
    return world.Formula(f.blueprint, total_time, f.output, new_items)


def powerset(iterable):
    s = list(iterable)
    return itertools.chain.from_iterable(
        itertools.combinations(s, r) for r in range(len(s) + 1)
    )


def fold_formula(
    f: world.Formula, others: Dict[int, world.Formula]
) -> List[world.Formula]:
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


def main():
    logging.basicConfig(level=logging.INFO)
    serv = services.Services()
    w = world.World(serv.reference_db)
    ipc = market.ItemPriceCache(serv.store_db, serv.api)

    formulas = [w.find_formula(w.find_item_type(id)) for id in REACTIONS]
    formulas_by_output = {f.output.item_type.id: f for f in formulas}
    priced = []
    for f in formulas:
        folded = [
            price_formula(ipc, f) for f in fold_formula(f, formulas_by_output)
        ]
        folded.sort(key=lambda p: p.profit_per_day, reverse=True)
        priced.append(folded[0])
    priced.sort(key=lambda p: p.profit_per_day, reverse=True)
    for p in priced:
        p.print(w, ipc)
        print()


if __name__ == "__main__":
    main()