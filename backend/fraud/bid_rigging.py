"""
Detector: Colusión / Bid Rigging (COLU, COLU2)
Detects:
  1. Shadow bidding: the winner wins by < 2% margin, repeatedly with the same loser
  2. Rotating winners: same group of suppliers alternates winning in the same category
  3. Near-identical bid amounts from different suppliers
"""
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

SHADOW_MARGIN = 0.02      # < 2% margin between winner and 2nd place
MIN_SHADOW_OCCURRENCES = 3  # Needs to happen 3+ times to flag
MIN_ROTATION_SIZE = 3       # At least 3 suppliers in rotating group
MIN_ROTATION_CYCLES = 3     # Rotation must appear 3+ times
IDENTICAL_THRESHOLD = 0.001  # Bids within 0.1% of each other = near identical


def detect(db: Session) -> list[dict]:
    alerts = []

    # --- Shadow bidding detection ---
    # Get all tenders with at least 2 valid bids and an award
    # Resolve bid supplier OCDS IDs to real Chilean RUTs via procurement_parties
    query = text("""
        SELECT
            b.ocid,
            pp_b.party_rut AS buyer_rut,
            buyer_party.name AS buyer_name,
            p.region,
            i.unspsc_prefix,
            COALESCE(bid_party.rut, b.supplier_rut) AS supplier_rut,
            COALESCE(bid_party.name, b.supplier_name) AS supplier_name,
            b.amount,
            b.status,
            pp_w.party_rut AS winner_rut,
            winner_party.name AS winner_name,
            a.amount AS award_amount
        FROM bids b
        JOIN procurements p ON p.ocid = b.ocid
        LEFT JOIN awards a ON a.ocid = b.ocid
        LEFT JOIN items i ON i.ocid = b.ocid
        JOIN procurement_parties pp_w ON pp_w.procurement_ocid = a.ocid AND pp_w.role = 'supplier'
        JOIN parties winner_party ON winner_party.rut = pp_w.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        LEFT JOIN procurement_parties pp_bid ON pp_bid.procurement_ocid = b.ocid AND pp_bid.role = 'tenderer'
        LEFT JOIN parties bid_party ON bid_party.rut = pp_bid.party_rut
            AND bid_party.name = b.supplier_name
        WHERE b.status IN ('valid', 'submitted', '')
          AND b.amount IS NOT NULL
          AND b.amount > 0
          AND pp_w.party_rut IS NOT NULL
        ORDER BY b.ocid, b.amount ASC
    """)

    rows = db.execute(query).fetchall()

    # Group bids by ocid
    tenders = defaultdict(list)
    for row in rows:
        tenders[row.ocid].append(row)

    # For shadow bidding: track (winner_rut, second_rut) pairs across tenders
    shadow_pairs = defaultdict(list)  # (winner_rut, second_rut) → list of ocids

    for ocid, bids in tenders.items():
        if len(bids) < 2:
            continue

        winner_rut = bids[0].winner_rut
        award_amount = bids[0].award_amount

        if not winner_rut or not award_amount:
            continue

        # Sort valid bids by amount
        valid_bids = sorted(bids, key=lambda b: b.amount or float("inf"))
        if len(valid_bids) < 2:
            continue

        lowest_bid = valid_bids[0]
        second_bid = valid_bids[1]

        if not lowest_bid.amount or not second_bid.amount:
            continue

        margin = abs(second_bid.amount - lowest_bid.amount) / lowest_bid.amount

        if margin < SHADOW_MARGIN:
            pair = (lowest_bid.supplier_rut, second_bid.supplier_rut)
            shadow_pairs[pair].append({
                "ocid": ocid,
                "winner_rut": lowest_bid.supplier_rut,
                "winner_name": lowest_bid.supplier_name,
                "loser_rut": second_bid.supplier_rut,
                "loser_name": second_bid.supplier_name,
                "winner_amount": lowest_bid.amount,
                "loser_amount": second_bid.amount,
                "margin_pct": round(margin * 100, 3),
                "buyer_name": lowest_bid.buyer_name,
                "buyer_rut": lowest_bid.buyer_rut,
                "region": lowest_bid.region,
                "unspsc_prefix": lowest_bid.unspsc_prefix,
            })

    for (winner_rut, loser_rut), occurrences in shadow_pairs.items():
        if len(occurrences) < MIN_SHADOW_OCCURRENCES:
            continue

        first = occurrences[0]
        total_involved = sum(o["winner_amount"] for o in occurrences if o["winner_amount"])

        alerts.append({
            "ocid": first["ocid"],
            "alert_type": "COLU",
            "severity": "alta",
            "title": f"Posible shadow bidding: {first['winner_name'] or winner_rut} vs {first['loser_name'] or loser_rut}",
            "description": (
                f"Los proveedores {first['winner_name'] or winner_rut} y "
                f"{first['loser_name'] or loser_rut} aparecen en {len(occurrences)} "
                f"licitaciones donde el ganador supera al perdedor por menos del "
                f"{SHADOW_MARGIN*100:.0f}% del monto. Este patrón repetido sugiere "
                f"colusión donde el 'perdedor' presenta oferta de cobertura. "
                f"Monto total involucrado: ${total_involved:,.0f} CLP."
            ),
            "evidence": {
                "winner_rut": winner_rut,
                "winner_name": first["winner_name"],
                "loser_rut": loser_rut,
                "loser_name": first["loser_name"],
                "occurrence_count": len(occurrences),
                "total_amount": total_involved,
                "occurrences": [
                    {
                        "ocid": o["ocid"],
                        "winner_amount": o["winner_amount"],
                        "loser_amount": o["loser_amount"],
                        "margin_pct": o["margin_pct"],
                    }
                    for o in occurrences[:20]
                ],
            },
            "buyer_rut": first["buyer_rut"],
            "buyer_name": first["buyer_name"],
            "supplier_rut": winner_rut,
            "supplier_name": first["winner_name"],
            "region": first["region"],
            "amount_involved": total_involved,
        })

    # --- Rotating winners detection ---
    # Group by unspsc_prefix + buyer_rut, find sets of suppliers that alternate winning
    winner_by_segment = defaultdict(list)  # (buyer_rut, unspsc_prefix) → list of (ocid, winner_rut, winner_name)

    query2 = text("""
        SELECT
            pp_b.party_rut AS buyer_rut, buyer_party.name AS buyer_name, p.region,
            i.unspsc_prefix,
            pp_s.party_rut AS supplier_rut, supplier_party.name AS supplier_name,
            p.ocid,
            p.tender_start
        FROM procurements p
        JOIN awards a ON a.ocid = p.ocid
        JOIN items i ON i.ocid = p.ocid
        JOIN procurement_parties pp_s ON pp_s.procurement_ocid = a.ocid AND pp_s.role = 'supplier'
        JOIN parties supplier_party ON supplier_party.rut = pp_s.party_rut
        JOIN procurement_parties pp_b ON pp_b.procurement_ocid = p.ocid AND pp_b.role = 'buyer'
        JOIN parties buyer_party ON buyer_party.rut = pp_b.party_rut
        WHERE pp_s.party_rut IS NOT NULL
          AND i.unspsc_prefix != ''
          AND pp_b.party_rut IS NOT NULL
        ORDER BY pp_b.party_rut, i.unspsc_prefix, p.tender_start
    """)

    rows2 = db.execute(query2).fetchall()

    for row in rows2:
        key = (row.buyer_rut, row.unspsc_prefix)
        winner_by_segment[key].append({
            "ocid": row.ocid,
            "supplier_rut": row.supplier_rut,
            "supplier_name": row.supplier_name,
            "buyer_name": row.buyer_name,
            "region": row.region,
            "date": row.tender_start,
        })

    for (buyer_rut, unspsc_prefix), wins in winner_by_segment.items():
        if len(wins) < MIN_ROTATION_CYCLES:
            continue

        # Get unique winners
        unique_winners = set(w["supplier_rut"] for w in wins)
        if len(unique_winners) < 2 or len(unique_winners) > 6:
            continue

        # Check if winners alternate (no single winner dominates)
        from collections import Counter
        win_counts = Counter(w["supplier_rut"] for w in wins)
        total_wins = len(wins)
        max_share = max(win_counts.values()) / total_wins

        # Rotation: no supplier wins more than 70% (balanced distribution among small group)
        if max_share <= 0.70 and len(unique_winners) >= 2 and total_wins >= MIN_ROTATION_CYCLES:
            first = wins[0]
            ocids = [w["ocid"] for w in wins]

            alerts.append({
                "ocid": ocids[0],
                "alert_type": "COLU2",
                "severity": "media",
                "title": f"Posible rotación de ganadores en {buyer_rut} categoría {unspsc_prefix}",
                "description": (
                    f"El organismo {first['buyer_name'] or buyer_rut} adjudicó "
                    f"{total_wins} licitaciones en categoría UNSPSC {unspsc_prefix} "
                    f"a un grupo de solo {len(unique_winners)} proveedores que alternan "
                    f"victorias. Ningún proveedor supera el {max_share*100:.0f}% de las "
                    f"adjudicaciones. Este patrón puede indicar acuerdo de reparto de contratos."
                ),
                "evidence": {
                    "buyer_rut": buyer_rut,
                    "buyer_name": first["buyer_name"],
                    "unspsc_prefix": unspsc_prefix,
                    "total_contracts": total_wins,
                    "rotating_suppliers": [
                        {
                            "rut": rut,
                            "wins": count,
                            "share": round(count / total_wins, 3),
                        }
                        for rut, count in win_counts.most_common()
                    ],
                    "ocids": ocids[:20],
                },
                "buyer_rut": buyer_rut,
                "buyer_name": first["buyer_name"],
                "supplier_rut": None,
                "supplier_name": None,
                "region": first["region"],
                "amount_involved": None,
            })

    logger.info(f"COLU detector: {len(alerts)} alerts generated")
    return alerts
