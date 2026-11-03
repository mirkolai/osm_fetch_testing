import csv
import json
import os
import re
from typing import Dict, List, Optional

_BASE_DIR = os.path.dirname(__file__)
_MAPPING_PATH = os.path.join(_BASE_DIR, "personalised_categories.tsv")
_CATEGORIES_PATH = os.path.join(_BASE_DIR, "categories.json")

_CACHE: Optional[Dict] = None


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def _load() -> Dict:
    """
    Legge personalised_categories.tsv e costruisce il mapping tra categorie originali
    (categories.json, indicizzate nel DB) e categorie personalizzate (New*).
    Le categorie originali assenti dal TSV sono escluse.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with open(_CATEGORIES_PATH, "r", encoding="utf-8") as file_obj:
        original_groups = json.load(file_obj)
    original_secondaries = {cat for values in original_groups.values() for cat in values}
    # Stesso ordine usato per indicizzare i vettori nel DB.
    original_secondary_list = sorted(original_secondaries)
    normalized_originals = {_norm(cat): cat for cat in original_secondaries}

    new_groups: Dict[str, List[str]] = {}
    new_to_originals: Dict[str, List[str]] = {}
    original_to_new: Dict[str, str] = {}

    with open(_MAPPING_PATH, "r", encoding="utf-8", newline="") as file_obj:
        for row in csv.DictReader(file_obj, delimiter="\t"):
            original = normalized_originals.get(_norm(row.get("Secondary", "")))
            new_primary = _norm(row.get("NewPrimaryName", ""))
            new_secondary = _norm(row.get("NewSecondaryName", ""))
            if original is None:
                raise ValueError(
                    f"personalised_categories.tsv: categoria '{row.get('Secondary')}' non presente in categories.json"
                )
            if not new_primary or not new_secondary:
                raise ValueError(f"personalised_categories.tsv: riga incompleta per '{original}'")
            if original in original_to_new:
                if original_to_new[original] != new_secondary:
                    raise ValueError(f"personalised_categories.tsv: '{original}' mappata su più categorie")
                continue

            original_to_new[original] = new_secondary
            new_to_originals.setdefault(new_secondary, []).append(original)
            secondaries = new_groups.setdefault(new_primary, [])
            if new_secondary not in secondaries:
                secondaries.append(new_secondary)

    _CACHE = {
        "original_secondary_list": original_secondary_list,
        "new_groups": new_groups,
        "new_to_originals": new_to_originals,
        "original_to_new": original_to_new,
    }
    return _CACHE


def get_new_groups() -> Dict[str, List[str]]:
    """NewPrimaryName -> [NewSecondaryName]."""
    return _load()["new_groups"]


def get_new_secondary_categories() -> List[str]:
    return [sec for secondaries in get_new_groups().values() for sec in secondaries]


def get_original_secondary_list() -> List[str]:
    """Categorie originali in ordine alfabetico (indici dei vettori nel DB)."""
    return _load()["original_secondary_list"]


def new_to_original_categories(new_secondary: str) -> List[str]:
    return _load()["new_to_originals"].get(new_secondary, [])


def original_to_new_category(original: str) -> Optional[str]:
    return _load()["original_to_new"].get(original)


def aggregate_secondary_counts(counts: List[int]) -> Dict[str, int]:
    """Somma i conteggi del DB (indicizzati per categoria originale) per NewSecondaryName."""
    data = _load()
    aggregated = {new_sec: 0 for new_sec in data["new_to_originals"]}
    for index, original in enumerate(data["original_secondary_list"]):
        new_sec = data["original_to_new"].get(original)
        if new_sec is not None and index < len(counts):
            aggregated[new_sec] += counts[index] or 0
    return aggregated


def expand_new_categories(categories: List[str]) -> List[str]:
    """Traduce NewPrimaryName/NewSecondaryName nelle categorie originali (POI)."""
    data = _load()
    expanded: List[str] = []
    for category in categories or []:
        if category in data["new_to_originals"]:
            expanded.extend(data["new_to_originals"][category])
        elif category in data["new_groups"]:
            for new_sec in data["new_groups"][category]:
                expanded.extend(data["new_to_originals"][new_sec])
    return list(dict.fromkeys(expanded))
