from __future__ import annotations

import argparse
import ast
import glob
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import pandas as pd


PERSON_ALIASES = {
    "donald trump": "donald_trump",
    "trump": "donald_trump",
    "vladimir putin": "vladimir_putin",
    "putin": "vladimir_putin",
    "volodymyr zelenskyy": "volodymyr_zelenskyy",
    "volodymyr zelensky": "volodymyr_zelenskyy",
    "volodomyr zelenskyy": "volodymyr_zelenskyy",
    "zelenskyy": "volodymyr_zelenskyy",
    "zelensky": "volodymyr_zelenskyy",
    "pope leo xiv": "pope_leo_xiv",
    "pope leo": "pope_leo_xiv",
    "xi jinping": "xi_jinping",
    "maduro": "nicolas_maduro",
    "nicolas maduro": "nicolas_maduro",
    "yoon": "yoon_suk_yeol",
    "yoon suk yeol": "yoon_suk_yeol",
    "powell": "jerome_powell",
    "jerome powell": "jerome_powell",
    "khamenei": "ali_khamenei",
    "ali khamenei": "ali_khamenei",
    "lula": "luiz_inacio_lula_da_silva",
    "luiz inacio lula da silva": "luiz_inacio_lula_da_silva",
    "luiz inácio lula da silva": "luiz_inacio_lula_da_silva",
}

PLACE_ALIASES = {
    "united states": "united_states",
    "usa": "united_states",
    "u.s.": "united_states",
    "us": "united_states",
    "ukraine": "ukraine",
    "the ukraine": "ukraine",
    "russia": "russia",
    "russian federation": "russia",
    "china": "china",
    "taiwan": "taiwan",
    "israel": "israel",
    "hamas": "hamas",
    "mar-a-lago": "mar_a_lago",
    "white house": "white_house",
}

PARTY_ALIASES = {
    "the democratic": "democratic_party",
    "democratic": "democratic_party",
    "the democratic party": "democratic_party",
    "democratic party": "democratic_party",
    "the republican": "republican_party",
    "republican": "republican_party",
    "the republican party": "republican_party",
    "republican party": "republican_party",
    "the conservative party": "conservative_party",
    "conservative party": "conservative_party",
    "the liberal party": "liberal_party",
    "liberal party": "liberal_party",
    "the green party": "green_party",
    "green party": "green_party",
    "the new democratic party": "new_democratic_party",
    "new democratic party": "new_democratic_party",
    "the people's party": "peoples_party",
    "people's party": "peoples_party",
}

TEAM_ALIASES = {
    "los angeles d": "los_angeles_dodgers",
    "los angeles dodgers": "los_angeles_dodgers",
    "la dodgers": "los_angeles_dodgers",
    "new york y": "new_york_yankees",
    "new york yankees": "new_york_yankees",
    "ny yankees": "new_york_yankees",
    "indiana": "indiana_pacers",
    "indiana pacers": "indiana_pacers",
    "sacramento kings": "sacramento_kings",
    "toronto raptors": "toronto_raptors",
    "aston villa": "aston_villa",
    "atlanta hawks": "atlanta_hawks",
    "hawks": "atlanta_hawks",
    "boston celtics": "boston_celtics",
    "celtics": "boston_celtics",
    "brooklyn nets": "brooklyn_nets",
    "nets": "brooklyn_nets",
    "charlotte hornets": "charlotte_hornets",
    "hornets": "charlotte_hornets",
    "chicago bulls": "chicago_bulls",
    "bulls": "chicago_bulls",
    "cleveland cavaliers": "cleveland_cavaliers",
    "cavaliers": "cleveland_cavaliers",
    "dallas mavericks": "dallas_mavericks",
    "mavericks": "dallas_mavericks",
    "denver nuggets": "denver_nuggets",
    "nuggets": "denver_nuggets",
    "detroit pistons": "detroit_pistons",
    "pistons": "detroit_pistons",
    "golden state warriors": "golden_state_warriors",
    "warriors": "golden_state_warriors",
    "houston rockets": "houston_rockets",
    "rockets": "houston_rockets",
    "la clippers": "los_angeles_clippers",
    "los angeles clippers": "los_angeles_clippers",
    "los angeles c": "los_angeles_clippers",
    "clippers": "los_angeles_clippers",
    "los angeles lakers": "los_angeles_lakers",
    "lakers": "los_angeles_lakers",
    "memphis grizzlies": "memphis_grizzlies",
    "grizzlies": "memphis_grizzlies",
    "miami heat": "miami_heat",
    "heat": "miami_heat",
    "milwaukee bucks": "milwaukee_bucks",
    "bucks": "milwaukee_bucks",
    "minnesota timberwolves": "minnesota_timberwolves",
    "timberwolves": "minnesota_timberwolves",
    "new orleans pelicans": "new_orleans_pelicans",
    "pelicans": "new_orleans_pelicans",
    "new york knicks": "new_york_knicks",
    "knicks": "new_york_knicks",
    "oklahoma city thunder": "oklahoma_city_thunder",
    "thunder": "oklahoma_city_thunder",
    "orlando magic": "orlando_magic",
    "magic": "orlando_magic",
    "philadelphia 76ers": "philadelphia_76ers",
    "76ers": "philadelphia_76ers",
    "phoenix suns": "phoenix_suns",
    "suns": "phoenix_suns",
    "portland trail blazers": "portland_trail_blazers",
    "trail blazers": "portland_trail_blazers",
    "san antonio spurs": "san_antonio_spurs",
    "spurs": "san_antonio_spurs",
    "utah jazz": "utah_jazz",
    "jazz": "utah_jazz",
    "washington wizards": "washington_wizards",
    "wizards": "washington_wizards",
    "arizona cardinals": "arizona_cardinals",
    "cardinals": "arizona_cardinals",
    "atlanta falcons": "atlanta_falcons",
    "atlanta": "atlanta_falcons",
    "baltimore ravens": "baltimore_ravens",
    "baltimore": "baltimore_ravens",
    "buffalo bills": "buffalo_bills",
    "buffalo": "buffalo_bills",
    "carolina panthers": "carolina_panthers",
    "chicago bears": "chicago_bears",
    "chicago": "chicago_bears",
    "cincinnati bengals": "cincinnati_bengals",
    "cincinnati": "cincinnati_bengals",
    "cleveland browns": "cleveland_browns",
    "cleveland": "cleveland_browns",
    "dallas cowboys": "dallas_cowboys",
    "dallas": "dallas_cowboys",
    "denver broncos": "denver_broncos",
    "denver": "denver_broncos",
    "detroit lions": "detroit_lions",
    "detroit": "detroit_lions",
    "green bay packers": "green_bay_packers",
    "green bay": "green_bay_packers",
    "houston texans": "houston_texans",
    "houston": "houston_texans",
    "indianapolis colts": "indianapolis_colts",
    "jacksonville jaguars": "jacksonville_jaguars",
    "kansas city chiefs": "kansas_city_chiefs",
    "kansas city": "kansas_city_chiefs",
    "las vegas raiders": "las_vegas_raiders",
    "raiders": "las_vegas_raiders",
    "los angeles chargers": "los_angeles_chargers",
    "los angeles rams": "los_angeles_rams",
    "los angeles r": "los_angeles_rams",
    "miami dolphins": "miami_dolphins",
    "minnesota vikings": "minnesota_vikings",
    "minnesota": "minnesota_vikings",
    "new england patriots": "new_england_patriots",
    "new orleans saints": "new_orleans_saints",
    "new york giants": "new_york_giants",
    "new york jets": "new_york_jets",
    "new york j": "new_york_jets",
    "philadelphia eagles": "philadelphia_eagles",
    "philadelphia": "philadelphia_eagles",
    "pittsburgh steelers": "pittsburgh_steelers",
    "pittsburgh": "pittsburgh_steelers",
    "san francisco 49ers": "san_francisco_49ers",
    "san francisco": "san_francisco_49ers",
    "seattle seahawks": "seattle_seahawks",
    "seattle": "seattle_seahawks",
    "tampa bay buccaneers": "tampa_bay_buccaneers",
    "tampa bay": "tampa_bay_buccaneers",
    "tennessee titans": "tennessee_titans",
    "tennessee": "tennessee_titans",
    "washington commanders": "washington_commanders",
    "commanders": "washington_commanders",
    "toronto blue jays": "toronto_blue_jays",
    "blue jays": "toronto_blue_jays",
    "seattle mariners": "seattle_mariners",
    "mariners": "seattle_mariners",
    "new york mets": "new_york_mets",
    "mets": "new_york_mets",
    "cleveland guardians": "cleveland_guardians",
    "guardians": "cleveland_guardians",
    "boston bruins": "boston_bruins",
    "bruins": "boston_bruins",
    "toronto maple leafs": "toronto_maple_leafs",
    "maple leafs": "toronto_maple_leafs",
    "washington capitals": "washington_capitals",
    "capitals": "washington_capitals",
    "new york rangers": "new_york_rangers",
    "rangers": "new_york_rangers",
    "nashville predators": "nashville_predators",
    "predators": "nashville_predators",
    "florida panthers": "florida_panthers",
    "panthers": "florida_panthers",
    "tampa bay lightning": "tampa_bay_lightning",
    "lightning": "tampa_bay_lightning",
    "vegas golden knights": "vegas_golden_knights",
    "golden knights": "vegas_golden_knights",
    "andrea kimi antonelli": "kimi_antonelli",
    "kimi antonelli": "kimi_antonelli",
    "carlos sainz jr": "carlos_sainz",
    "carlos sainz": "carlos_sainz",
    "max verstappen": "max_verstappen",
    "lewis hamilton": "lewis_hamilton",
    "charles leclerc": "charles_leclerc",
    "george russell": "george_russell",
    "oscar piastri": "oscar_piastri",
    "lando norris": "lando_norris",
    "esteban ocon": "esteban_ocon",
    "pierre gasly": "pierre_gasly",
    "lance stroll": "lance_stroll",
    "juventus": "juventus",
    "inter milan": "inter_milan",
    "napoli": "napoli",
    "atalanta": "atalanta",
    "as roma": "as_roma",
    "roma": "as_roma",
    "bayern munich": "bayern_munich",
    "bayer leverkusen": "bayer_leverkusen",
    "stuttgart": "stuttgart",
    "dynamo kyiv": "dynamo_kyiv",
    "t1": "t1",
    "ohio st": "ohio_state",
    "ohio state": "ohio_state",
    "miami (fl)": "miami_fl",
    "alabama": "alabama",
    "georgia": "georgia",
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

UMA_VALUE_PATTERN = re.compile(r"\b(uma|optimistic\s+oracle|oo\s*v?2|oo\s*v?3)\b", re.I)
RESOLVER_COLUMN_PATTERN = re.compile(r"(uma|oracle|resolver|resolution|adapter|arbitrator)", re.I)

EVENT_WINDOW_PRESETS = {
    "suit_mineral_5d": [
        ("mineral_rights", "2025-03-19", "2025-03-29"),
        ("zelensky_suit", "2025-06-25", "2025-07-13"),
    ]
}

LEAGUE_SLUG_PREFIXES = {
    "nba": "nba_game",
    "nhl": "nhl_game",
    "mlb": "mlb_game",
    "nfl": "nfl_game",
    "cbb": "cbb_game",
    "cfb": "cfb_game",
    "cwbb": "cwbb_game",
}


@dataclass
class ParsedContract:
    market_family: str = ""
    predicate: str = ""
    subject: str = ""
    obj: str = ""
    scope: str = ""
    deadline: str = ""
    season: str = ""
    threshold: str = ""
    direction: str = ""
    contract_key: str = ""
    entity_signature: str = ""
    parse_confidence: float = 0.0
    parse_reason: str = ""


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = text.replace("**", "")
    text = text.replace("’", "'")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_list_like(value: object) -> list:
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    text = str(value).strip()
    if not text:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, list):
            return parsed
    return []


def slugify(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def canonical_alias(value: str, aliases: dict[str, str] | None = None) -> str:
    text = clean_text(value).strip(" ?.,")
    if aliases and text in aliases:
        return aliases[text]
    return slugify(text)


def canonical_team(value: object, row: pd.Series | None = None, scope: str = "") -> str:
    label = clean_text(value).strip(" ?.,")
    if not label:
        return ""

    ticker = clean_text(row.get("ticker", "")) if row is not None else ""
    if scope.startswith("nba") or ticker.startswith("kxnba"):
        nba_city = {
            "atlanta": "atlanta_hawks",
            "boston": "boston_celtics",
            "brooklyn": "brooklyn_nets",
            "charlotte": "charlotte_hornets",
            "chicago": "chicago_bulls",
            "cleveland": "cleveland_cavaliers",
            "denver": "denver_nuggets",
            "detroit": "detroit_pistons",
            "golden state": "golden_state_warriors",
            "houston": "houston_rockets",
            "indiana": "indiana_pacers",
            "los angeles c": "los_angeles_clippers",
            "los angeles l": "los_angeles_lakers",
            "memphis": "memphis_grizzlies",
            "miami": "miami_heat",
            "milwaukee": "milwaukee_bucks",
            "minnesota": "minnesota_timberwolves",
            "new orleans": "new_orleans_pelicans",
            "new york": "new_york_knicks",
            "oklahoma city": "oklahoma_city_thunder",
            "orlando": "orlando_magic",
            "philadelphia": "philadelphia_76ers",
            "phoenix": "phoenix_suns",
            "portland": "portland_trail_blazers",
            "sacramento": "sacramento_kings",
            "san antonio": "san_antonio_spurs",
            "toronto": "toronto_raptors",
            "utah": "utah_jazz",
            "washington": "washington_wizards",
        }
        if label in nba_city:
            return nba_city[label]

    if scope.startswith("mlb") or ticker.startswith("kxmlb"):
        mlb_city = {
            "los angeles d": "los_angeles_dodgers",
            "new york y": "new_york_yankees",
            "new york m": "new_york_mets",
            "toronto": "toronto_blue_jays",
            "seattle": "seattle_mariners",
            "cleveland": "cleveland_guardians",
        }
        if label in mlb_city:
            return mlb_city[label]

    return canonical_alias(label, TEAM_ALIASES | PLACE_ALIASES)


def outcome_name(row: pd.Series) -> str:
    return clean_text(row.get("outcome_name", ""))


def first_alias_in_text(text: str, aliases: dict[str, str]) -> str:
    text = clean_text(text)
    for label in sorted(aliases, key=len, reverse=True):
        if re.search(rf"\b{re.escape(label)}\b", text):
            return aliases[label]
    return ""


def infer_context_year(row: pd.Series) -> str:
    for col in ("end_date", "close_time", "end_ts", "close_ts", "created_at", "created_time"):
        value = row.get(col)
        if pd.notna(value):
            match = re.search(r"\b(20\d{2})\b", str(value))
            if match:
                return match.group(1)
    return ""


def extract_deadline(text: str, row: pd.Series) -> str:
    text = clean_text(text)

    if "first 100 days" in text:
        return "period:first_100_days"
    if "first year" in text:
        return "period:first_year"

    match = re.search(r"\bbefore\s+(20\d{2})\b", text)
    if match:
        return f"year:{int(match.group(1)) - 1}"

    match = re.search(r"\bin\s+(20\d{2})\b", text)
    if match:
        return f"year:{match.group(1)}"

    match = re.search(r"\b(before|by)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2}),?\s+(20\d{2})", text)
    if match:
        qualifier = match.group(1)
        month = MONTHS[match.group(2)]
        day = int(match.group(3))
        year = int(match.group(4))
        if qualifier == "before" and month == 1 and day == 1:
            return f"year:{year - 1}"
        if qualifier == "by" and month == 12 and day == 31:
            return f"year:{year}"
        return f"{qualifier}:{year:04d}-{month:02d}-{day:02d}"

    match = re.search(r"\b(before|by)\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})\b", text)
    if match:
        year = infer_context_year(row)
        qualifier = match.group(1)
        month = MONTHS[match.group(2)]
        day = int(match.group(3))
        if year:
            return f"{qualifier}:{year}-{month:02d}-{day:02d}"
        return f"{qualifier}_month_day:{month:02d}-{day:02d}"

    match = re.search(r"\bby\s+(dec(?:ember)?|jan(?:uary)?)\s+31,?\s+(20\d{2})", text)
    if match and MONTHS[match.group(1)] == 12:
        return f"year:{match.group(2)}"

    match = re.search(r"\bbefore\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", text)
    if match:
        year = infer_context_year(row)
        month = MONTHS[match.group(1)]
        return f"before:{year}-{month:02d}-01" if year else f"before_month:{month:02d}"

    match = re.search(r"\bby\s+december\s+31,?\s+(20\d{2})", text)
    if match:
        return f"year:{match.group(1)}"

    return ""


def make_key(parsed: ParsedContract) -> ParsedContract:
    fields = [
        parsed.market_family,
        parsed.predicate,
        parsed.subject,
        parsed.obj,
        parsed.scope,
        parsed.deadline,
        parsed.season,
        parsed.direction,
        parsed.threshold,
    ]
    parsed.contract_key = "|".join(str(f) for f in fields if str(f))
    parsed.entity_signature = "|".join(
        str(f)
        for f in [parsed.market_family, parsed.predicate, parsed.subject, parsed.obj, parsed.scope, parsed.season, parsed.direction, parsed.threshold]
        if str(f)
    )
    return parsed


def normalize_meeting_participants(parsed: ParsedContract) -> ParsedContract:
    if parsed.predicate == "meet" and parsed.subject and parsed.obj:
        parsed.subject, parsed.obj = sorted([parsed.subject, parsed.obj])
    return parsed


def parse_leader_contact(text: str, row: pd.Series) -> ParsedContract | None:
    if "meet with" not in text and "visit" not in text:
        return None

    if re.search(r"\b(first|next)\b", text) and not re.search(r"\bwill\s+.+\s+(meet with|visit)\b", text):
        return None

    predicate = "meet" if "meet with" in text else "visit"
    subject = ""
    obj = ""

    if predicate == "meet":
        before, after = text.split("meet with", 1)
        subject = first_alias_in_text(before, PERSON_ALIASES)
        obj = first_alias_in_text(after, PERSON_ALIASES)
    else:
        before = text.split("visit", 1)[0]
        subject = first_alias_in_text(before, PERSON_ALIASES)
        match = re.search(r"\bvisit\s+([a-z.\- ]+?)(?:\s+in\b|\s+before\b|\s+by\b|\?|$)", text)
        if match:
            obj = canonical_alias(match.group(1), PLACE_ALIASES)

    if not subject and predicate == "visit" and "trump" in text:
        subject = "donald_trump"

    if not subject or not obj:
        return None

    parsed = ParsedContract(
        market_family="leader_contact",
        predicate=predicate,
        subject=subject,
        obj=obj,
        deadline=extract_deadline(text, row),
        parse_confidence=0.92,
        parse_reason="leader contact template",
    )
    return make_key(normalize_meeting_participants(parsed))


def parse_office_exit(text: str, row: pd.Series) -> ParsedContract | None:
    person = first_alias_in_text(text, PERSON_ALIASES)
    if not person:
        return None

    if re.search(r"\bresigns?\b", text):
        predicate = "resign"
    elif "call for" in text and "impeach" in text:
        predicate = "call_for_impeachment"
    elif "convict" in text and "impeachment" in text:
        predicate = "convict_impeachment"
    elif re.search(r"\bbe impeached\b|\bimpeached in\b", text):
        predicate = "impeached"
    elif "removed from office" in text:
        predicate = "removed_from_office"
    elif re.search(r"\bout as .*(?:president|fed chair|supreme leader)\b|\bfirst leader out\b|\bout this year\b|\bout in 20\d{2}\b|\bleaves? before\b", text):
        predicate = "leave_office"
    elif re.search(r"\breinstated as president\b", text):
        predicate = "reinstated"
    else:
        return None

    deadline = extract_deadline(text, row)
    if not deadline and "this year" in text:
        context_year = infer_context_year(row)
        deadline = f"year:{context_year}" if context_year else ""

    parsed = ParsedContract(
        market_family="office_exit",
        predicate=predicate,
        subject=person,
        deadline=deadline,
        parse_confidence=0.88,
        parse_reason="office exit template",
    )
    return make_key(parsed)


def parse_election(text: str, row: pd.Series) -> ParsedContract | None:
    if "election" not in text and "mayor race" not in text:
        return None

    deadline = extract_deadline(text, row)
    year_match = re.search(r"\b(20\d{2})\b", text)
    season = year_match.group(1) if year_match else deadline.replace("year:", "")

    if "ukraine" in text and "presidential election" in text:
        predicate = "hold_election"
        scope = "ukraine_presidential"
    elif "ukraine election called" in text:
        predicate = "election_called"
        scope = "ukraine_presidential"
    elif "nyc mayor" in text or "new york city mayor" in text:
        predicate = "win"
        scope = "nyc_mayor_candidate"
        party_match = re.search(r"representative of the (.+?) party", text)
        candidate_match = re.search(r"will\s+(.+?)\s+win\s+the\s+20\d{2}\s+nyc mayor", text)
        if party_match:
            scope = "nyc_mayor_party_line"
            subject = canonical_alias(party_match.group(1))
        elif candidate_match:
            subject = canonical_alias(candidate_match.group(1))
        else:
            subject = canonical_alias(row.get("yes_sub_title", ""))
    else:
        return None

    if scope != "nyc_mayor_candidate" and scope != "nyc_mayor_party_line":
        subject = first_alias_in_text(text, PARTY_ALIASES)
        if not subject:
            subject = first_alias_in_text(text, PERSON_ALIASES)
    if not deadline and season:
        deadline = f"year:{season}"

    parsed = ParsedContract(
        market_family="election",
        predicate=predicate,
        subject=subject,
        scope=scope,
        deadline=deadline,
        season=season,
        parse_confidence=0.86,
        parse_reason="election template",
    )
    return make_key(parsed)


def parse_candidate_office(text: str, row: pd.Series) -> ParsedContract | None:
    outcome = outcome_name(row)
    label = outcome or clean_text(row.get("yes_sub_title", ""))
    subject = ""
    scope = ""
    predicate = "win"
    season_match = re.search(r"\b(20\d{2})\b", text)
    season = season_match.group(1) if season_match else ""

    patterns = [
        (r"will\s+(.+?)\s+win\s+the\s+(20\d{2}\s+)?new jersey gubernatorial election", "new_jersey_governor"),
        (r"will\s+(.+?)\s+win\s+the\s+irish presidential election", "irish_president"),
        (r"will\s+(.+?)\s+win\s+the\s+romanian presidential election", "romanian_president"),
        (r"will\s+(.+?)\s+be\s+the\s+next president of poland", "poland_president"),
        (r"will\s+(.+?)\s+be\s+the\s+next canadian prime minister", "canadian_prime_minister"),
        (r"will\s+(.+?)\s+win\s+the\s+canadian prime ministry", "canadian_prime_minister"),
        (r"will\s+(.+?)\s+be\s+appointed as the next florida senator", "florida_senator"),
        (r"will\s+(.+?)\s+be\s+the first elected speaker of the house", "us_house_speaker_119"),
    ]
    for pattern, found_scope in patterns:
        match = re.search(pattern, text)
        if match:
            subject = canonical_alias(match.group(1))
            scope = found_scope
            break

    if "win the canadian prime ministry" in text and outcome:
        subject = canonical_alias(label, PARTY_ALIASES)
        scope = "canadian_prime_minister"

    if "nominee for the nyc mayorship" in text:
        predicate = "nominee"
        scope = "nyc_mayor_democratic_nominee" if "democratic party" in text else "nyc_mayor_nominee"
        subject = canonical_alias(label)
        season = season or "2025"

    if not subject or not scope:
        return None

    deadline = extract_deadline(text, row)
    if not deadline and season:
        deadline = f"year:{season}"
    parsed = ParsedContract(
        market_family="election",
        predicate=predicate,
        subject=subject,
        scope=scope,
        deadline=deadline,
        season=season,
        parse_confidence=0.84,
        parse_reason="candidate office template",
    )
    return make_key(parsed)


def scope_from_election_phrase(phrase: str) -> str:
    phrase = clean_text(phrase)
    phrase = re.sub(r"\b20\d{2}\b", "", phrase)
    phrase = re.sub(r"\b(?:the|next|following|after)\b", "", phrase)
    phrase = re.sub(r"\s+", " ", phrase).strip(" ?.,")
    replacements = [
        ("new jersey governor election", "new_jersey_governor"),
        ("new jersey gubernatorial election", "new_jersey_governor"),
        ("virginia gubernatorial election", "virginia_governor"),
        ("wisconsin supreme court seat", "wisconsin_supreme_court"),
        ("romanian presidential election", "romanian_president"),
        ("first round of bolivian presidential election", "bolivia_president_first_round"),
        ("first round of the bolivian presidential election", "bolivia_president_first_round"),
        ("bolivian presidential election", "bolivia_president"),
        ("bolivia presidential election", "bolivia_president"),
        ("chilean presidential election", "chile_president"),
        ("netherlands parliamentary election", "netherlands_parliament"),
        ("norwegian parliamentary election", "norway_parliament"),
        ("portuguese legislative election", "portugal_parliament"),
        ("portuguese general election", "portugal_parliament"),
        ("albanian parliamentary election", "albania_parliament"),
        ("canadian house of commons election", "canada_federal"),
        ("canadian election", "canada_federal"),
        ("argentina election", "argentina_chamber_of_deputies"),
        ("democratic presidential nominee", "us_democratic_presidential_nominee"),
        ("democratic presidential nomination", "us_democratic_presidential_nominee"),
        ("democratic primary for mayor of new york city", "nyc_mayor_democratic_primary"),
        ("mayor of new york city", "nyc_mayor"),
        ("mayor of seattle", "seattle_mayor"),
        ("mayor of bucharest", "bucharest_mayor"),
    ]
    for source, target in replacements:
        if source in phrase:
            return target
    phrase = phrase.replace(" election", "")
    return slugify(phrase)


def parse_generic_election_winner(text: str, row: pd.Series) -> ParsedContract | None:
    label = outcome_name(row) or clean_text(row.get("yes_sub_title", ""))
    subject = ""
    scope = ""
    predicate = "win"
    season_match = re.search(r"\b(20\d{2})\b", text)
    season = season_match.group(1) if season_match else ""

    most_seats_match = re.search(r"will\s+(.+?)\s+win\s+the\s+most seats\s+in\s+the\s+(.+?election)", text)
    if most_seats_match:
        predicate = "win_most_seats"
        subject = canonical_alias(most_seats_match.group(1), PARTY_ALIASES)
        scope = scope_from_election_phrase(most_seats_match.group(2))

    patterns = [
        r"will\s+(.+?)\s+win\s+the\s+(.+?(?:election|race|seat))",
        r"will\s+(.+?)\s+win\s+the\s+(.+?primary\s+for\s+mayor\s+of\s+new york city)",
        r"will\s+(.+?)\s+win\s+the\s+election\s+for\s+the\s+(.+?)\s+in\s+20\d{2}",
        r"will\s+(.+?)\s+be\s+the\s+(.+?nominee)\s+in\s+20\d{2}",
        r"will\s+(.+?)\s+win\s+(.+?nomination)\s+in\s+20\d{2}",
    ]
    if not subject:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                subject = canonical_alias(match.group(1), PARTY_ALIASES)
                scope = scope_from_election_phrase(match.group(2))
                break

    if not subject:
        match = re.search(r"who\s+will\s+win\s+the\s+(.+?election)", text)
        if match and label:
            subject = canonical_alias(label, PARTY_ALIASES)
            scope = scope_from_election_phrase(match.group(1))

    if not subject:
        match = re.search(r"(.+?)\s+win\s+majority\s+in\s+(.+?election)", text)
        if match:
            predicate = "win_majority"
            subject = canonical_alias(match.group(1), PARTY_ALIASES)
            scope = scope_from_election_phrase(match.group(2))

    if not subject and "win the canadian prime ministry" in text and label:
        subject = canonical_alias(label, PARTY_ALIASES)
        scope = "canadian_prime_minister"

    if not subject or not scope:
        return None

    deadline = extract_deadline(text, row)
    if not season:
        season = deadline.replace("year:", "") or infer_context_year(row)
    if not deadline and season:
        deadline = f"year:{season}"

    parsed = ParsedContract(
        market_family="election",
        predicate=predicate,
        subject=subject,
        scope=scope,
        deadline=deadline,
        season=season,
        parse_confidence=0.78,
        parse_reason="generic election winner template",
    )
    return make_key(parsed)


def parse_sports(text: str, row: pd.Series) -> ParsedContract | None:
    if "qualify" in text:
        predicate = "qualify"
    elif re.search(r"\bwins?\b", text) or "drivers champion" in text:
        predicate = "win"
    else:
        return None

    league_patterns = [
        ("formula_1_drivers_championship", r"formula 1 drivers championship|drivers champion"),
        ("nba_finals", r"nba finals|pro basketball championship"),
        ("nba_eastern_conference", r"eastern conference|nba eastern conference"),
        ("nba_western_conference", r"western conference|nba western conference"),
        ("mlb_championship", r"pro baseball championship|world series|mlb"),
        ("mlb_american_league", r"american league championship"),
        ("mlb_national_league", r"national league championship"),
        ("premier_league", r"premier league"),
        ("serie_a", r"serie a"),
        ("bundesliga", r"bundesliga|german bundesliga"),
        ("uefa_europa_league", r"uefa europa league|europa league"),
        ("league_worlds", r"league worlds"),
        ("college_football_playoff", r"college football playoff national championship"),
        ("nhl_presidents_trophy", r"president.s trophy"),
        ("la_liga", r"la liga"),
        ("march_madness", r"march madness|college basketball d1 championship"),
        ("womens_march_madness", r"women's college basketball d1 championship"),
        ("uefa_champions_league", r"uefa champions league|champions league"),
        ("fifa_world_cup", r"fifa world cup|men's world cup|mens world cup|world cup"),
        ("nfl_super_bowl", r"super bowl|nfl championship"),
        ("nhl_stanley_cup", r"stanley cup|nhl"),
        ("masters", r"masters"),
        ("us_open_golf", r"us open championship"),
        ("the_open_golf", r"the open championship"),
        ("pga_championship", r"pga championship"),
        ("wimbledon_mens", r"wimbledon"),
        ("french_open_mens", r"french open men's singles championship"),
        ("us_open_tennis_mens", r"men's us open"),
        ("us_open_tennis_womens", r"us open women's tennis"),
        ("french_open_womens", r"french open women's singles championship"),
        ("ryder_cup", r"ryder cup"),
    ]
    scope = ""
    for league, pattern in league_patterns:
        if re.search(pattern, text):
            scope = league
            break
    if not scope:
        ticker = clean_text(row.get("ticker", ""))
        if ticker.startswith("kxmarmad"):
            scope = "march_madness"
        elif ticker.startswith("kxwmarmad"):
            scope = "womens_march_madness"
        elif ticker.startswith("kxsb-"):
            scope = "nfl_super_bowl"
    if not scope:
        return None

    subject = ""
    match = re.search(r"will\s+(?:the\s+)?(.+?)\s+win\s+the\b", text)
    if match:
        subject = canonical_team(match.group(1), row, scope)
    if not subject and scope == "formula_1_drivers_championship":
        match = re.search(r"will\s+(?:the\s+)?(.+?)\s+be\s+the\s+(?:20\d{2}\s+)?drivers champion", text)
        if match:
            subject = canonical_team(match.group(1), row, scope)
    if not subject and predicate == "win":
        match = re.search(r"^(.+?)\s+wins?\s+the\b", text)
        if match:
            subject = canonical_team(match.group(1), row, scope)
    if not subject and predicate == "qualify":
        match = re.search(r"will\s+(?:the\s+)?(.+?)\s+qualify\b", text)
        if match:
            subject = canonical_team(match.group(1), row, scope)

    if not subject:
        subject = canonical_team(row.get("yes_sub_title", "") or outcome_name(row), row, scope)

    season_match = re.search(r"\b(20\d{2})\b", text)
    season = season_match.group(1) if season_match else ""
    if not season:
        ticker = clean_text(row.get("ticker", ""))
        ticker_match = re.search(r"-(\d{2})(?:-|$)", ticker)
        if ticker_match:
            season = f"20{ticker_match.group(1)}"

    parsed = ParsedContract(
        market_family="sports",
        predicate=predicate,
        subject=subject,
        scope=scope,
        season=season,
        parse_confidence=0.86,
        parse_reason="sports outcome template",
    )
    return make_key(parsed)


def parse_sports_award_or_prop(text: str, row: pd.Series) -> ParsedContract | None:
    label = outcome_name(row) or clean_text(row.get("yes_sub_title", ""))
    subject = canonical_team(label, row) if label else ""
    scope = ""
    predicate = "win"
    season = infer_context_year(row)

    patterns = [
        ("nba_assists_leader", "lead", r"lead\s+the\s+nba\s+in\s+assists"),
        ("nba_scoring_leader", "lead", r"lead\s+the\s+nba\s+in\s+scoring"),
        ("nfl_mvp", "win", r"who\s+will\s+win\s+mvp|nflmvp"),
        ("mlb_al_mvp", "win", r"who\s+will\s+win\s+al mvp|al mvp"),
        ("mlb_nl_rookie_of_year", "win", r"who\s+will\s+win\s+nl rookie of the year|nl rookie"),
        ("super_bowl_halftime_headliner", "headline", r"headline\s+the\s+pro football championship halftime show"),
        ("emmy_drama_series", "win", r"drama series at the emmy awards"),
    ]
    for found_scope, found_predicate, pattern in patterns:
        if re.search(pattern, text):
            scope = found_scope
            predicate = found_predicate
            break
    if not scope:
        return None

    if not subject:
        match = re.search(r"will\s+(.+?)\s+lead\s+the\s+nba", text)
        if match:
            subject = canonical_alias(match.group(1))
    if not subject and label:
        subject = canonical_alias(label)
    if not subject:
        return None

    year_match = re.search(r"\b(20\d{2})\b", text)
    season = year_match.group(1) if year_match else season
    parsed = ParsedContract(
        market_family="sports_prop",
        predicate=predicate,
        subject=subject,
        scope=scope,
        season=season,
        parse_confidence=0.76,
        parse_reason="sports award/prop template",
    )
    return make_key(parsed)


def parse_sports_game(text: str, row: pd.Series) -> ParsedContract | None:
    slug = clean_text(row.get("slug", ""))
    outcome = outcome_name(row)
    selected = outcome or clean_text(row.get("yes_sub_title", ""))

    scope = ""
    game_date = ""
    slug_match = re.search(r"\b(nba|nhl|mlb|nfl|cbb|cfb|cwbb)-[a-z0-9]+-[a-z0-9]+-(20\d{2})-(\d{2})-(\d{2})\b", slug)
    if slug_match:
        scope = LEAGUE_SLUG_PREFIXES.get(slug_match.group(1), "")
        game_date = f"{slug_match.group(2)}-{slug_match.group(3)}-{slug_match.group(4)}"

    if not scope:
        ticker = clean_text(row.get("ticker", ""))
        ticker_match = re.search(r"kx(nfl)game-(\d{2})([a-z]{3})(\d{2})", ticker)
        if ticker_match:
            scope = "nfl_game"
            month = MONTHS.get(ticker_match.group(3), 0)
            game_date = f"20{ticker_match.group(2)}-{month:02d}-{int(ticker_match.group(4)):02d}"

    if not scope and re.search(r"\b.+?\s+vs\.?\s+.+?\b", text):
        scope = "generic_head_to_head"

    if not scope:
        return None

    teams_match = re.search(r"(.+?)\s+vs\.?\s+(.+?)(?:\s+\(|\s+-|\?|$)", text)
    participants = []
    if teams_match:
        participants = [
            canonical_team(teams_match.group(1), row, scope),
            canonical_team(teams_match.group(2), row, scope),
        ]
    participants = sorted([p for p in participants if p])
    subject = canonical_team(selected, row, scope)
    if not subject:
        beat_match = re.search(r"will\s+(.+?)\s+beat\s+(.+?)(?:\s+by\b|\?|$)", text)
        if beat_match:
            subject = canonical_team(beat_match.group(1), row, scope)
            participants = sorted([canonical_team(beat_match.group(1), row, scope), canonical_team(beat_match.group(2), row, scope)])

    if not subject or len(participants) < 2:
        return None

    parsed = ParsedContract(
        market_family="sports_game",
        predicate="win",
        subject=subject,
        scope=scope,
        deadline=game_date,
        season=game_date[:4] if game_date else "",
        obj="__".join(participants),
        parse_confidence=0.82,
        parse_reason="sports game winner template",
    )
    return make_key(parsed)


def parse_fed_count_or_level(text: str, row: pd.Series) -> ParsedContract | None:
    if "fed" not in text and "federal reserve" not in text and "federal funds rate" not in text:
        return None

    cut_count_match = re.search(r"(?:will\s+)?(?:the\s+)?fed\s+cut\s+rates?\s+(\d+)\s+times?", text)
    pm_cut_count_match = re.search(r"will\s+(no|\d+\+?)\s+fed\s+rate\s+cuts?\s+happen\s+in\s+(20\d{2})", text)
    if cut_count_match or pm_cut_count_match:
        if cut_count_match:
            count = cut_count_match.group(1)
            direction = "equal"
        else:
            raw_count = pm_cut_count_match.group(1)
            count = "0" if raw_count == "no" else raw_count.replace("+", "")
            direction = "at_least" if raw_count.endswith("+") else "equal"
        season_match = re.search(r"\b(20\d{2})\b", text)
        season = season_match.group(1) if season_match else deadline_from_ticker(row).replace("year:", "")
        scope = "fed_emergency_rate_cuts" if "emergency" in text else "fed_rate_cuts"
        parsed = ParsedContract(
            market_family="fed_count",
            predicate="cut",
            scope=scope,
            season=season,
            direction=direction,
            threshold=count,
            parse_confidence=0.82,
            parse_reason="fed rate cut count template",
        )
        return make_key(parsed)

    level_match = re.search(r"upper bound of the federal funds rate be above\s+(\d+(?:\.\d+)?)%.*?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),\s+(20\d{2})", text)
    if level_match:
        threshold = level_match.group(1)
        month = MONTHS[level_match.group(2)]
        day = int(level_match.group(3))
        year = int(level_match.group(4))
        parsed = ParsedContract(
            market_family="fed_rate_level",
            predicate="upper_bound",
            scope=f"fed_meeting:{year:04d}-{month:02d}-{day:02d}",
            direction="above",
            threshold=threshold,
            parse_confidence=0.8,
            parse_reason="fed funds level template",
        )
        return make_key(parsed)

    return None


def parse_fed_decision(text: str, row: pd.Series) -> ParsedContract | None:
    if "fed" not in text and "federal reserve" not in text:
        return None
    month_match = re.search(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(20\d{2})\s+meeting", text)
    if not month_match:
        ticker = clean_text(row.get("ticker", ""))
        ticker_match = re.search(r"feddecision-(\d{2})([a-z]{3})", ticker)
        if ticker_match:
            month = MONTHS.get(ticker_match.group(2), 0)
            scope = f"fed_meeting:20{ticker_match.group(1)}-{month:02d}"
        else:
            return None
    else:
        scope = f"fed_meeting:{month_match.group(2)}-{MONTHS[month_match.group(1)]:02d}"

    if "no change" in text or "maintains rate" in text or "hike rates by 0bps" in text:
        predicate = "hold"
        threshold = "0"
        direction = "hold"
    elif "cut" in text or "decreases" in text:
        predicate = "cut"
        direction = "greater_than" if ">" in text or "+" in text else "equal"
        match = re.search(r"(?:by\s+|rates\s+by\s+)(?:>|>=)?\s*(\d+)\s*bps", text)
        threshold = match.group(1) if match else ""
    elif "hike" in text or "increases" in text:
        predicate = "hike"
        direction = "greater_than" if ">" in text or "+" in text else "equal"
        match = re.search(r"(?:by\s+|rates\s+by\s+)(?:>|>=)?\s*(\d+)\s*bps", text)
        threshold = match.group(1) if match else ""
    else:
        return None

    parsed = ParsedContract(
        market_family="fed_decision",
        predicate=predicate,
        scope=scope,
        direction=direction,
        threshold=threshold,
        parse_confidence=0.86,
        parse_reason="fed decision template",
    )
    return make_key(parsed)


def parse_crypto_threshold(text: str, row: pd.Series) -> ParsedContract | None:
    asset_match = re.search(r"\b(bitcoin|btc|ethereum|solana|\$trump|official trump)\b", text)
    if not asset_match:
        return None
    asset = {
        "btc": "bitcoin",
        "$trump": "official_trump",
        "official trump": "official_trump",
    }.get(asset_match.group(1), asset_match.group(1))

    first_match = re.search(r"hit\s+\$?([\d.]+)\s*k?\s+or\s+\$?([\d.]+)\s*k?\s+first", text)
    if first_match:
        subject = outcome_name(row).replace("$", "")
        threshold = canonical_alias(subject) if subject else ""
        parsed = ParsedContract(
            market_family="asset_threshold_race",
            predicate="hit_first",
            subject=asset,
            threshold=threshold,
            deadline=extract_deadline(text, row),
            parse_confidence=0.8,
            parse_reason="asset threshold race template",
        )
        return make_key(parsed)

    ladder_match = re.search(r"how\s+(high|low)\s+will\s+(bitcoin|btc|ethereum|solana)\s+get", text)
    if ladder_match:
        label = clean_text(row.get("yes_sub_title", ""))
        threshold_match = re.search(r"\$?([\d,]+(?:\.\d+)?)", label)
        if not threshold_match:
            return None
        parsed = ParsedContract(
            market_family="asset_threshold",
            predicate="threshold",
            subject=asset,
            deadline=extract_deadline(text, row) or deadline_from_ticker(row),
            direction="above" if ladder_match.group(1) == "high" else "below",
            threshold=normalize_price_threshold(threshold_match.group(1)),
            parse_confidence=0.82,
            parse_reason="asset threshold ladder template",
        )
        return make_key(parsed)

    dip_match = re.search(r"\bdip\s+to\s+\$?([\d,]+)", text)
    if dip_match:
        parsed = ParsedContract(
            market_family="asset_threshold",
            predicate="threshold",
            subject=asset,
            threshold=normalize_price_threshold(dip_match.group(1)),
            deadline=extract_deadline(text, row),
            direction="below",
            parse_confidence=0.82,
            parse_reason="asset below threshold template",
        )
        return make_key(parsed)

    reach_match = re.search(r"(?:reach|hit)\s+\$?([\d,]+)", text)
    if reach_match:
        parsed = ParsedContract(
            market_family="asset_threshold",
            predicate="threshold",
            subject=asset,
            threshold=normalize_price_threshold(reach_match.group(1)),
            deadline=extract_deadline(text, row),
            direction="above",
            parse_confidence=0.82,
            parse_reason="asset threshold template",
        )
        return make_key(parsed)

    return None


def normalize_price_threshold(value: str) -> str:
    number = value.replace(",", "")
    if "." in number:
        as_float = float(number)
        if as_float.is_integer():
            return str(int(as_float))
    return number


def deadline_from_ticker(row: pd.Series) -> str:
    ticker = clean_text(row.get("ticker", ""))
    match = re.search(r"-(\d{2})-?dec31", ticker)
    if match:
        return f"year:20{match.group(1)}"
    match = re.search(r"-(\d{2})(?:-|$)", ticker)
    if match:
        return f"year:20{match.group(1)}"
    return ""


def parse_market_leader(text: str, row: pd.Series) -> ParsedContract | None:
    scopes = [
        ("largest_company_by_market_cap", r"largest company in the world by market cap"),
        ("top_ai_model", r"top ai model|best ai at year end|best ai in mar"),
    ]
    scope = ""
    for found_scope, pattern in scopes:
        if re.search(pattern, text):
            scope = found_scope
            break
    if not scope:
        return None

    subject = outcome_name(row) or clean_text(row.get("yes_sub_title", ""))
    if not subject:
        if scope == "largest_company_by_market_cap":
            match = re.search(r"will\s+(.+?)\s+be\s+the\s+largest company", text)
        else:
            match = re.search(r"will\s+(.+?)\s+have\s+the\s+top ai model", text)
        if match:
            subject = match.group(1)
    if not subject:
        return None

    parsed = ParsedContract(
        market_family="market_leader",
        predicate="lead",
        subject=canonical_alias(subject),
        scope=scope,
        deadline=extract_deadline(text, row) or deadline_from_ticker(row),
        season=(re.search(r"\b(20\d{2})\b", text).group(1) if re.search(r"\b(20\d{2})\b", text) else infer_context_year(row)),
        parse_confidence=0.78,
        parse_reason="market leader template",
    )
    return make_key(parsed)


def parse_geopolitical_event(text: str, row: pd.Series) -> ParsedContract | None:
    if "ceasefire" in text:
        pairs = [
            ("russia", "ukraine", r"russia\s*x\s*ukraine|russia-ukraine|ukraine"),
            ("israel", "hamas", r"israel\s*x\s*hamas"),
        ]
        for subject, obj, pattern in pairs:
            if re.search(pattern, text):
                parsed = ParsedContract(
                    market_family="geopolitical_event",
                    predicate="ceasefire",
                    subject=subject,
                    obj=obj,
                    deadline=extract_deadline(text, row),
                    parse_confidence=0.8,
                    parse_reason="ceasefire template",
                )
                return make_key(parsed)

    if re.search(r"(?:china invade taiwan|china invades taiwan)", text):
        parsed = ParsedContract(
            market_family="geopolitical_event",
            predicate="invade",
            subject="china",
            obj="taiwan",
            deadline=extract_deadline(text, row),
            parse_confidence=0.8,
            parse_reason="invasion template",
        )
        return make_key(parsed)

    if re.search(r"trump ends? ukraine war|end(?:s)? (?:the )?war in ukraine", text):
        parsed = ParsedContract(
            market_family="geopolitical_event",
            predicate="end_war",
            subject="donald_trump",
            obj="ukraine_war",
            deadline=extract_deadline(text, row),
            parse_confidence=0.78,
            parse_reason="war-end template",
        )
        return make_key(parsed)

    if re.search(r"ukraine agrees? to trump mineral deal", text):
        parsed = ParsedContract(
            market_family="geopolitical_event",
            predicate="agreement",
            subject="ukraine",
            obj="trump_mineral_deal",
            deadline=extract_deadline(text, row),
            parse_confidence=0.78,
            parse_reason="mineral deal template",
        )
        return make_key(parsed)

    return None


def parse_policy_action(text: str, row: pd.Series) -> ParsedContract | None:
    state_reserve_match = re.search(r"\b(texas|north carolina)\s+strategic bitcoin reserve act", text)
    if state_reserve_match:
        parsed = ParsedContract(
            market_family="policy_action",
            predicate="pass_law",
            subject="strategic_bitcoin_reserve_act",
            obj=canonical_alias(state_reserve_match.group(1), PLACE_ALIASES),
            deadline=extract_deadline(text, row) or extract_deadline(clean_text(row.get("yes_sub_title", "")), row) or deadline_from_ticker(row),
            parse_confidence=0.8,
            parse_reason="state bitcoin reserve law template",
        )
        return make_key(parsed)

    templates = [
        ("tiktok_ban", "ban", "united_states", r"tiktok (?:be )?banned|tiktok leave the app store"),
        ("tiktok_sale", "sale_announced", "united_states", r"tiktok sale announced"),
        ("epstein_documents", "release", "united_states", r"release any documents about epstein"),
        ("recession", "start", "united_states", r"^(?:will\s+)?(?:(?:us|u\.s\.|united states)\s+)?recession\b|there be a recession"),
        ("department_of_education", "eliminate", "united_states", r"department of education (?:be )?eliminated|end department of education"),
        ("national_bitcoin_reserve", "create", "united_states", r"(?:national bitcoin reserve|trump create bitcoin reserve|us national bitcoin reserve)"),
        ("aliens_exist", "confirm", "united_states", r"confirm(?:s)? (?:that )?aliens exist"),
        ("ufo_files", "release", "united_states", r"(?:release|declassif(?:y|ies)) (?:new )?ufo files"),
        ("greenland", "acquire", "united_states", r"(?:buy|acquire) greenland|united states acquire any part of greenland"),
    ]
    for subject, predicate, obj, pattern in templates:
        if not re.search(pattern, text):
            continue
        parsed = ParsedContract(
            market_family="policy_action",
            predicate=predicate,
            subject=subject,
            obj=obj,
            deadline=extract_deadline(text, row) or extract_deadline(clean_text(row.get("yes_sub_title", "")), row) or deadline_from_ticker(row),
            parse_confidence=0.78,
            parse_reason="policy action template",
        )
        return make_key(parsed)
    return None


def parse_media_winner(text: str, row: pd.Series) -> ParsedContract | None:
    scopes = [
        ("top_grossing_movie", r"top grossing movie"),
        ("domestic_opening_weekend", r"best domestic opening weekend"),
        ("eurovision", r"eurovision"),
    ]
    scope = ""
    for found_scope, pattern in scopes:
        if re.search(pattern, text):
            scope = found_scope
            break
    if not scope:
        return None

    subject = outcome_name(row) or clean_text(row.get("yes_sub_title", ""))
    if not subject:
        if scope == "eurovision":
            match = re.search(r"will\s+(.+?)\s+win\s+eurovision", text)
        elif scope == "domestic_opening_weekend":
            match = re.search(r"will\s+['\"]?(.+?)['\"]?\s+have\s+the\s+best domestic opening weekend", text)
        else:
            match = re.search(r"will\s+(.+?)\s+be\s+the\s+top grossing movie", text)
        if match:
            subject = match.group(1)
    if not subject:
        return None

    parsed = ParsedContract(
        market_family="media",
        predicate="win",
        subject=canonical_alias(subject),
        scope=scope,
        season=(re.search(r"\b(20\d{2})\b", text).group(1) if re.search(r"\b(20\d{2})\b", text) else infer_context_year(row)),
        parse_confidence=0.8,
        parse_reason="media winner template",
    )
    return make_key(parsed)


def parse_award_winner(text: str, row: pd.Series) -> ParsedContract | None:
    scopes = [
        ("nobel_peace_prize", r"nobel peace prize"),
        ("best_picture_oscar", r"best picture oscar"),
        ("top_spotify_artist", r"top spotify artist"),
    ]
    scope = ""
    for found_scope, pattern in scopes:
        if re.search(pattern, text):
            scope = found_scope
            break
    if not scope:
        return None

    subject = canonical_alias(outcome_name(row) or row.get("yes_sub_title", ""))
    if not subject:
        match = re.search(r"will\s+(.+?)\s+win", text)
        if match:
            subject = canonical_alias(match.group(1))
    if not subject:
        return None

    season_match = re.search(r"\b(20\d{2})\b", text)
    season = season_match.group(1) if season_match else infer_context_year(row)
    parsed = ParsedContract(
        market_family="award",
        predicate="win",
        subject=subject,
        scope=scope,
        season=season,
        parse_confidence=0.82,
        parse_reason="award winner template",
    )
    return make_key(parsed)


def parse_economic_threshold(text: str, row: pd.Series) -> ParsedContract | None:
    if not re.search(r"\babove\b|\bbelow\b|\breach\b", text):
        return None

    indicator_patterns = [
        ("thirty_year_fixed_mortgage_rate", r"30[- ]year fixed rate mortgage|30-year fixed rate mortgage|mortgage rate"),
        ("new_home_sales", r"new u\.?s\.? home sales|new home sales"),
    ]
    scope = ""
    for indicator, pattern in indicator_patterns:
        if re.search(pattern, text):
            scope = indicator
            break
    if not scope:
        return None

    direction = "above" if "above" in text else "below" if "below" in text else ""
    threshold_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*%?", text)
    threshold = threshold_match.group(1).replace(",", "") if threshold_match else ""

    parsed = ParsedContract(
        market_family="economic_threshold",
        predicate="threshold",
        scope=scope,
        deadline=extract_deadline(text, row),
        direction=direction,
        threshold=threshold,
        parse_confidence=0.84,
        parse_reason="economic threshold template",
    )
    return make_key(parsed)


def parse_market(exchange: str, row: pd.Series) -> ParsedContract:
    title_col = "question" if exchange == "polymarket" else "title"
    title = clean_text(row.get(title_col, ""))

    parsers = [
        parse_leader_contact,
        parse_office_exit,
        parse_election,
        parse_candidate_office,
        parse_generic_election_winner,
        parse_sports_game,
        parse_sports_award_or_prop,
        parse_sports,
        parse_fed_count_or_level,
        parse_fed_decision,
        parse_crypto_threshold,
        parse_market_leader,
        parse_geopolitical_event,
        parse_policy_action,
        parse_award_winner,
        parse_media_winner,
        parse_economic_threshold,
    ]
    for parser in parsers:
        parsed = parser(title, row)
        if parsed and parsed.contract_key:
            return parsed
    return ParsedContract(parse_reason="no supported template")


def row_id(exchange: str, row: pd.Series) -> str:
    return str(row.get("id" if exchange == "polymarket" else "ticker", ""))


def event_group(exchange: str, row: pd.Series) -> str:
    return str(row.get("condition_id" if exchange == "polymarket" else "event_ticker", ""))


def expand_polymarket_rows(df: pd.DataFrame) -> list[pd.Series]:
    rows: list[pd.Series] = []
    for _, row in df.iterrows():
        outcomes = parse_list_like(row.get("outcomes"))
        token_ids = parse_list_like(row.get("clob_token_ids"))
        normalized = [clean_text(x) for x in outcomes]
        is_yes_no = len(normalized) == 2 and normalized[0] == "yes" and normalized[1] == "no"

        if not outcomes or is_yes_no:
            expanded = row.copy()
            expanded["outcome_index"] = 0 if is_yes_no else ""
            expanded["outcome_name"] = "Yes" if is_yes_no else ""
            expanded["token_id"] = str(token_ids[0]) if token_ids else ""
            expanded["synthetic_binary"] = False
            rows.append(expanded)
            continue

        for idx, outcome in enumerate(outcomes):
            expanded = row.copy()
            expanded["outcome_index"] = idx
            expanded["outcome_name"] = str(outcome).strip()
            expanded["token_id"] = str(token_ids[idx]) if idx < len(token_ids) else ""
            expanded["synthetic_binary"] = True
            rows.append(expanded)
    return rows


def canonicalize(exchange: str, df: pd.DataFrame, source_slug: str = "") -> pd.DataFrame:
    records = []
    title_col = "question" if exchange == "polymarket" else "title"
    source_rows: Iterable[pd.Series]
    source_rows = expand_polymarket_rows(df) if exchange == "polymarket" else (row for _, row in df.iterrows())
    for row in source_rows:
        parsed = parse_market(exchange, row)
        record = {
            "exchange": exchange,
            "source_slug": source_slug,
            "market_id": row_id(exchange, row),
            "event_group": event_group(exchange, row),
            "outcome_index": row.get("outcome_index", ""),
            "outcome_name": row.get("outcome_name", ""),
            "token_id": row.get("token_id", ""),
            "synthetic_binary": row.get("synthetic_binary", False),
            "title": row.get(title_col, ""),
            "yes_sub_title": row.get("yes_sub_title", ""),
            "no_sub_title": row.get("no_sub_title", ""),
            "volume": row.get("volume", ""),
            "created_at": row.get("created_at", row.get("created_time", "")),
            "end_date": row.get("end_date", row.get("close_time", "")),
            "resolver_type": row.get("resolver_type", ""),
            "resolver_evidence": row.get("resolver_evidence", ""),
        }
        record.update(asdict(parsed))
        records.append(record)
    return pd.DataFrame(records)


def resolver_columns(df: pd.DataFrame) -> list[str]:
    generated = {"resolver_type", "resolver_evidence"}
    return [col for col in df.columns if col not in generated and RESOLVER_COLUMN_PATTERN.search(str(col))]


def annotate_pm_resolver_type(pm_df: pd.DataFrame) -> pd.DataFrame:
    pm_df = pm_df.copy()
    cols = resolver_columns(pm_df)
    resolver_types = []
    evidence = []
    for _, row in pm_df.iterrows():
        hits = []
        for col in cols:
            value = row.get(col)
            if pd.notna(value) and UMA_VALUE_PATTERN.search(str(value)):
                hits.append(f"{col}={value}")
        resolver_types.append("uma" if hits else "")
        evidence.append("; ".join(hits))
    pm_df["resolver_type"] = resolver_types
    pm_df["resolver_evidence"] = evidence
    return pm_df


def read_market_key_set(path: str) -> dict[str, set[str]]:
    df = pd.read_csv(path)
    key_map: dict[str, set[str]] = {}
    for col in ("id", "market_id", "pm_id", "condition_id", "slug"):
        if col in df.columns:
            key_map[col] = set(df[col].dropna().astype(str))
    if not key_map:
        raise ValueError("--pm-uma-markets must contain at least one of: id, market_id, pm_id, condition_id, slug.")
    return key_map


def apply_pm_uma_filter(pm_df: pd.DataFrame, uma_path: str = "", uma_only: bool = False) -> pd.DataFrame:
    pm_df = annotate_pm_resolver_type(pm_df)
    if uma_path:
        key_map = read_market_key_set(uma_path)
        mask = pd.Series(False, index=pm_df.index)
        for source_col, values in key_map.items():
            col = "id" if source_col in {"market_id", "pm_id"} and "id" in pm_df.columns else source_col
            if col in pm_df.columns:
                mask = mask | pm_df[col].astype(str).isin(values)
        pm_df = pm_df[mask].copy()
        pm_df["resolver_type"] = "uma"
        current = pm_df.get("resolver_evidence", pd.Series("", index=pm_df.index)).fillna("").astype(str)
        pm_df["resolver_evidence"] = current.mask(current.eq(""), f"external_list:{Path(uma_path).name}")
        return pm_df

    if uma_only:
        detected = pm_df["resolver_type"].eq("uma")
        if detected.any():
            return pm_df[detected].copy()
        cols = resolver_columns(pm_df)
        raise ValueError(
            "No UMA-resolved Polymarket rows were detected. "
            f"Resolver-like columns found: {cols or 'none'}. "
            "Pass --pm-uma-markets with id, market_id, pm_id, condition_id, or slug to define the UMA sample."
        )

    return pm_df


def load_topic_pairs(exports_dir: Path, pm_uma_markets: str = "", pm_uma_only: bool = False) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    pairs = []
    for pm_path in sorted(exports_dir.glob("*_pm_topics.csv")):
        slug = pm_path.name[: -len("_pm_topics.csv")]
        k_path = exports_dir / f"{slug}_k_topics.csv"
        if not k_path.exists():
            continue
        pm_df = apply_pm_uma_filter(pd.read_csv(pm_path), pm_uma_markets, pm_uma_only)
        pairs.append((slug, pm_df, pd.read_csv(k_path)))
    return pairs


def event_filter_condition(created_col: str, end_col: str, preset: str) -> str:
    windows = EVENT_WINDOW_PRESETS.get(preset, [])
    if not windows:
        return "TRUE"
    clauses = []
    for _, start, end in windows:
        clauses.append(
            f"({created_col} <= TIMESTAMP '{start}' AND COALESCE({end_col}, TIMESTAMP '2100-01-01') >= TIMESTAMP '{end}')"
        )
    return "(" + " OR ".join(clauses) + ")"


def load_archive_markets(data_root: Path, top_n: int, pm_uma_markets: str = "", pm_uma_only: bool = False, event_preset: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required for --data-root archive loading.") from exc

    con = duckdb.connect()
    pm_files = glob.glob(str(data_root / "polymarket" / "markets" / "**" / "*.parquet"), recursive=True)
    k_files = glob.glob(str(data_root / "kalshi" / "markets" / "**" / "*.parquet"), recursive=True)
    if not pm_files or not k_files:
        raise FileNotFoundError("Could not find both Polymarket and Kalshi market parquet files.")

    pm_limit = "LIMIT ?" if top_n > 0 else ""
    k_limit = "LIMIT ?" if top_n > 0 else ""
    pm_event_filter = event_filter_condition("created_ts", "end_ts", event_preset)
    k_event_filter = event_filter_condition("created_ts", "close_ts", event_preset)
    pm_sql = f"""
        WITH base AS (
            SELECT id, condition_id, question, slug, outcomes, outcome_prices,
                   clob_token_ids, volume, liquidity,
                   active, closed, end_date, created_at, _fetched_at,
                   TRY_CAST(created_at AS TIMESTAMP) AS created_ts,
                   TRY_CAST(end_date AS TIMESTAMP) AS end_ts,
                   TRY_CAST(volume AS DOUBLE) AS volume_num,
                   ROW_NUMBER() OVER (
                       PARTITION BY id
                       ORDER BY TRY_CAST(_fetched_at AS TIMESTAMP) DESC
                   ) AS rn
            FROM read_parquet(?)
        )
        SELECT id, condition_id, question, slug, outcomes, outcome_prices,
               clob_token_ids, volume, liquidity,
               active, closed, end_date, created_at, _fetched_at
        FROM base
        WHERE rn = 1
          AND {pm_event_filter}
        ORDER BY COALESCE(volume_num, 0) DESC
        {pm_limit}
    """
    k_sql = f"""
        WITH base AS (
            SELECT ticker, event_ticker, market_type, title, yes_sub_title, no_sub_title,
                   status, yes_bid, yes_ask, no_bid, no_ask, last_price, volume,
                   open_interest, result, created_time, close_time, _fetched_at,
                   TRY_CAST(created_time AS TIMESTAMP) AS created_ts,
                   TRY_CAST(close_time AS TIMESTAMP) AS close_ts,
                   TRY_CAST(volume AS DOUBLE) AS volume_num,
                   ROW_NUMBER() OVER (
                       PARTITION BY ticker
                       ORDER BY TRY_CAST(_fetched_at AS TIMESTAMP) DESC
                   ) AS rn
            FROM read_parquet(?)
        )
        SELECT ticker, event_ticker, market_type, title, yes_sub_title, no_sub_title,
               status, yes_bid, yes_ask, no_bid, no_ask, last_price, volume,
               open_interest, result, created_time, close_time, _fetched_at
        FROM base
        WHERE rn = 1
          AND {k_event_filter}
        ORDER BY COALESCE(volume_num, 0) DESC
        {k_limit}
    """
    pm_args = [pm_files, top_n] if top_n > 0 else [pm_files]
    k_args = [k_files, top_n] if top_n > 0 else [k_files]
    pm_df = con.execute(pm_sql, pm_args).fetchdf()
    pm_df = apply_pm_uma_filter(pm_df, pm_uma_markets, pm_uma_only)
    return pm_df, con.execute(k_sql, k_args).fetchdf()


def compare_rows(pm: pd.Series, k: pd.Series) -> str:
    checks = [
        "market_family",
        "predicate",
        "subject",
        "obj",
        "scope",
        "deadline",
        "season",
        "direction",
        "threshold",
    ]
    reasons = []
    for col in checks:
        left = str(pm.get(col, ""))
        right = str(k.get(col, ""))
        if left != right:
            reasons.append(f"{col}_mismatch:{left or '<blank>'}!={right or '<blank>'}")
    return "; ".join(reasons) or "same_contract_key"


def build_matches(canonical: pd.DataFrame) -> pd.DataFrame:
    parsed = canonical[canonical["contract_key"].astype(str).ne("")].copy()
    parsed = parsed.drop_duplicates(subset=["exchange", "market_id", "contract_key"])
    pm = parsed[parsed["exchange"].eq("polymarket")]
    k = parsed[parsed["exchange"].eq("kalshi")]
    matches = pm.merge(k, on="contract_key", suffixes=("_pm", "_kalshi"))
    if matches.empty:
        return matches
    matches["match_confidence"] = matches[["parse_confidence_pm", "parse_confidence_kalshi"]].min(axis=1)
    matches["match_basis"] = "deterministic_contract_key"
    return matches.sort_values(["match_confidence", "contract_key"], ascending=[False, True])


def build_review_candidates(canonical: pd.DataFrame, max_pairs_per_bucket: int = 200) -> pd.DataFrame:
    parsed = canonical[canonical["market_family"].astype(str).ne("")].copy()
    parsed = parsed.drop_duplicates(subset=["exchange", "market_id", "contract_key"])
    pm = parsed[parsed["exchange"].eq("polymarket")]
    k = parsed[parsed["exchange"].eq("kalshi")]
    rows = []
    for signature, pm_bucket in pm.groupby("entity_signature"):
        if not signature:
            continue
        k_bucket = k[k["entity_signature"].eq(signature)]
        if k_bucket.empty:
            continue
        count = 0
        for _, pm_row in pm_bucket.iterrows():
            for _, k_row in k_bucket.iterrows():
                if pm_row["contract_key"] == k_row["contract_key"]:
                    continue
                rows.append(
                    {
                        "entity_signature": signature,
                        "pm_market_id": pm_row["market_id"],
                        "pm_title": pm_row["title"],
                        "pm_contract_key": pm_row["contract_key"],
                        "kalshi_market_id": k_row["market_id"],
                        "kalshi_title": k_row["title"],
                        "kalshi_contract_key": k_row["contract_key"],
                        "reject_reason": compare_rows(pm_row, k_row),
                    }
                )
                count += 1
                if count >= max_pairs_per_bucket:
                    break
            if count >= max_pairs_per_bucket:
                break
    return pd.DataFrame(rows)


def consolidate_canonical(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return canonical
    group_cols = [col for col in canonical.columns if col != "source_slug"]
    out = (
        canonical.groupby(group_cols, dropna=False)["source_slug"]
        .apply(lambda s: ";".join(sorted(set(str(x) for x in s if str(x)))))
        .reset_index()
    )
    cols = list(canonical.columns)
    return out[cols]


def write_outputs(canonical_frames: Iterable[pd.DataFrame], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    canonical = consolidate_canonical(pd.concat(list(canonical_frames), ignore_index=True))
    matches = build_matches(canonical)
    review = build_review_candidates(canonical)

    canonical.to_csv(outdir / "contract_canonical_markets.csv", index=False)
    matches.to_csv(outdir / "contract_matches.csv", index=False)
    review.to_csv(outdir / "contract_match_review_candidates.csv", index=False)

    print(f"Canonical markets: {len(canonical):,} -> {outdir / 'contract_canonical_markets.csv'}")
    print(f"Rule matches:      {len(matches):,} -> {outdir / 'contract_matches.csv'}")
    print(f"Review candidates: {len(review):,} -> {outdir / 'contract_match_review_candidates.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build high-precision cross-exchange market matches.")
    parser.add_argument("--exports-dir", default="exports", help="Directory containing *_pm_topics.csv and *_k_topics.csv files.")
    parser.add_argument("--data-root", default="", help="Optional full archive data root containing kalshi/ and polymarket/.")
    parser.add_argument("--top-n", type=int, default=5000, help="In archive mode, keep the top N latest unique markets by volume per exchange. Use 0 for all.")
    parser.add_argument("--event-preset", default="", choices=["", *EVENT_WINDOW_PRESETS.keys()], help="Optional archive-mode event-active filter preset.")
    parser.add_argument("--kalshi-csv", default="", help="Optional Kalshi market CSV.")
    parser.add_argument("--polymarket-csv", default="", help="Optional Polymarket market CSV.")
    parser.add_argument("--pm-uma-only", action="store_true", help="Restrict Polymarket inputs to rows detected as UMA-resolved.")
    parser.add_argument("--pm-uma-markets", default="", help="CSV defining UMA-resolved PM markets by id, market_id, pm_id, condition_id, or slug.")
    parser.add_argument("--outdir", default="exports", help="Output directory.")
    args = parser.parse_args()

    frames = []
    if args.kalshi_csv and args.polymarket_csv:
        pm_df = apply_pm_uma_filter(pd.read_csv(args.polymarket_csv), args.pm_uma_markets, args.pm_uma_only)
        frames.append(canonicalize("polymarket", pm_df, "custom"))
        frames.append(canonicalize("kalshi", pd.read_csv(args.kalshi_csv), "custom"))
    elif args.data_root:
        pm_df, k_df = load_archive_markets(Path(args.data_root), args.top_n, args.pm_uma_markets, args.pm_uma_only, args.event_preset)
        frames.append(canonicalize("polymarket", pm_df, "archive"))
        frames.append(canonicalize("kalshi", k_df, "archive"))
    else:
        pairs = load_topic_pairs(Path(args.exports_dir), args.pm_uma_markets, args.pm_uma_only)
        if not pairs:
            raise FileNotFoundError(f"No *_pm_topics.csv / *_k_topics.csv pairs found in {args.exports_dir}.")
        for slug, pm_df, k_df in pairs:
            frames.append(canonicalize("polymarket", pm_df, slug))
            frames.append(canonicalize("kalshi", k_df, slug))

    write_outputs(frames, Path(args.outdir))


if __name__ == "__main__":
    main()
