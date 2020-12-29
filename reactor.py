import logging

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
    46187,  # Unrefined Vanadium Hafnite Reaction Formula
    46188,  # Unrefined Platinum Technite Reaction Formula
    46189,  # Unrefined Solerium Reaction Formula
    46190,  # Unrefined Caesarium Cadmide Reaction Formula
    46191,  # Unrefined Hexite Reaction Formula
    46192,  # Unrefined Rolled Tungsten Alloy Reaction Formula
    46193,  # Unrefined Titanium Chromide Reaction Formula
    46194,  # Unrefined Fernite Alloy Reaction Formula
    46195,  # Unrefined Crystallite Alloy Reaction Formula
    46196,  # Unrefined Hyperflurite Reaction Formula
    46197,  # Unrefined Ferrofluid Reaction Formula
    46198,  # Unrefined Prometium Reaction Formula
    46199,  # Unrefined Neo Mercurite Reaction Formula
    46200,  # Unrefined Dysporite Reaction Formula
    46201,  # Unrefined Fluxed Condensates Reaction Formula
    46202,  # Unrefined Thulium Hafnite Reaction Formula
    46203,  # Unrefined Promethium Mercurite Reaction Formula
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


def price_formula(
    w: world.World, ipc: market.ItemPriceCache, id: int, verbose: bool = False
):
    blueprint = w.find_item_type(id)
    f = w.find_formula(blueprint)

    p = ipc.find_item_price(f.output.item_type)
    amt = p.low_price * f.output.quantity
    total = amt
    if verbose:
        print(f.time)
        print(
            f"{amt:15,.0f} {f.output.quantity}x {f.output.item_type.name}; "
            f"volume (runs): {p.daily_trade_volume / f.output.quantity:,.0f}"
        )

    for inp in f.inputs:
        p = ipc.find_item_price(inp.item_type)
        amt = -p.high_price * inp.quantity
        total += amt
        if verbose:
            print(
                f"{amt:15,.0f} {inp.quantity}x {inp.item_type.name}; "
                f"volume (runs): {p.daily_trade_volume / inp.quantity:,.0f}"
            )

    if verbose:
        print(f"= {total:13,.0f} per run")

    return total


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
    profits = [(price_formula(w, ipc, r), r) for r in REACTIONS]
    profits.sort(reverse=True)
    for _, r in profits:
        price_formula(w, ipc, r, verbose=True)


if __name__ == "__main__":
    main()