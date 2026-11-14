"""Localisation, currency and time.

Reference: docs/04-core.md ("Globalisation") and docs/07-experience.md (the jargon
map). Deliverable 15.

Three things, and the honest boundary between them:

    a message catalogue       five locales, with the jargon map as the interface vocabulary
    a formatter               numbers, currency, dates and times, per locale and per user timezone
    a length budget           a proxy for "renders without truncation", and it is a proxy

The specification's criterion says "five locales render without truncation on the
twelve highest-traffic screens". There are no screens in this repository, so the
test that can run here checks that every message exists in every locale and fits
a declared character budget. That catches the two failures a translation
introduces - a missing string and a string that outgrows its control - and it does
not catch a layout that was already broken in English.

Currency conversion uses the rate **effective on the transaction date**, never
today's rate. A forecast that converts a March deal at September's rate is a
number nobody can reconcile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

LOCALES = ("en", "es", "fr", "de", "pt")
BASE_LOCALE = "en"


@dataclass(frozen=True)
class LocaleMeta:
    code: str
    name: str
    rtl: bool = False
    decimal_separator: str = "."
    thousands_separator: str = ","
    date_order: str = "DMY"          # how a date is read, not how it is printed
    default_currency: str = "INR"


META = {
    "en": LocaleMeta("en", "English", default_currency="INR"),
    "es": LocaleMeta("es", "Espanol", decimal_separator=",", thousands_separator=".",
                     default_currency="EUR"),
    "fr": LocaleMeta("fr", "Francais", decimal_separator=",", thousands_separator=" ",
                     default_currency="EUR"),
    "de": LocaleMeta("de", "Deutsch", decimal_separator=",", thousands_separator=".",
                     default_currency="EUR"),
    "pt": LocaleMeta("pt", "Portugues", decimal_separator=",", thousands_separator=".",
                     default_currency="EUR"),
    # RTL is a layout mode, not a shipped locale. v1 supports the mechanism and
    # ships no RTL language; this pseudo-locale is what the mechanism is tested
    # against. Shipping a half-translated RTL language would be worse than
    # shipping the mechanism.
    "ar-x-mirror": LocaleMeta("ar-x-mirror", "RTL mirror (test)", rtl=True),
}

# The interface vocabulary is the jargon map from docs/07-experience.md. These
# keys are the interface's nouns; the test asserts every one has five locales.
CATALOGUE: dict[str, dict[str, str]] = {
    "nav.contacts": {"en": "Contacts", "es": "Contactos", "fr": "Contacts",
                     "de": "Kontakte", "pt": "Contatos"},
    "nav.companies": {"en": "Companies", "es": "Empresas", "fr": "Entreprises",
                      "de": "Unternehmen", "pt": "Empresas"},
    "nav.deals": {"en": "Deals", "es": "Oportunidades", "fr": "Affaires",
                  "de": "Vorgaenge", "pt": "Negocios"},
    "nav.activity": {"en": "Activity", "es": "Actividad", "fr": "Activite",
                     "de": "Aktivitaet", "pt": "Atividade"},
    "nav.history": {"en": "History", "es": "Historial", "fr": "Historique",
                    "de": "Verlauf", "pt": "Historico"},
    "nav.settings": {"en": "Settings", "es": "Ajustes", "fr": "Parametres",
                     "de": "Einstellungen", "pt": "Configuracoes"},
    "action.save": {"en": "Save", "es": "Guardar", "fr": "Enregistrer",
                    "de": "Speichern", "pt": "Guardar"},
    "action.cancel": {"en": "Cancel", "es": "Cancelar", "fr": "Annuler",
                      "de": "Abbrechen", "pt": "Cancelar"},
    "action.delete": {"en": "Delete", "es": "Eliminar", "fr": "Supprimer",
                      "de": "Loeschen", "pt": "Excluir"},
    "action.edit": {"en": "Edit", "es": "Editar", "fr": "Modifier",
                    "de": "Bearbeiten", "pt": "Editar"},
    "action.new": {"en": "New", "es": "Nuevo", "fr": "Nouveau", "de": "Neu",
                   "pt": "Novo"},
    "action.close": {"en": "Close", "es": "Cerrar", "fr": "Fermer",
                     "de": "Schliessen", "pt": "Fechar"},
    "action.next": {"en": "Next", "es": "Siguiente", "fr": "Suivant",
                    "de": "Weiter", "pt": "Proximo"},
    "action.back": {"en": "Back", "es": "Atras", "fr": "Retour", "de": "Zurueck",
                    "pt": "Voltar"},
    "search.placeholder": {"en": "Search everything", "es": "Buscar todo",
                           "fr": "Rechercher partout", "de": "Alles durchsuchen",
                           "pt": "Pesquisar tudo"},
    "state.empty": {"en": "Nothing here yet", "es": "Aun no hay nada",
                    "fr": "Rien pour le moment", "de": "Noch nichts vorhanden",
                    "pt": "Ainda nao ha nada"},
    "state.loading": {"en": "Loading", "es": "Cargando", "fr": "Chargement",
                      "de": "Wird geladen", "pt": "Carregando"},
    "field.required": {"en": "Required", "es": "Obligatorio", "fr": "Obligatoire",
                       "de": "Erforderlich", "pt": "Obrigatorio"},
    # the jargon map: internal term on the left in the docs, interface term here
    "term.connected_system": {"en": "Connected system", "es": "Sistema conectado",
                              "fr": "Systeme connecte", "de": "Verbundenes System",
                              "pt": "Sistema conectado"},
    "term.workspace": {"en": "Workspace", "es": "Espacio de trabajo",
                       "fr": "Espace de travail", "de": "Arbeitsbereich",
                       "pt": "Area de trabalho"},
    "term.position": {"en": "Position", "es": "Puesto", "fr": "Poste",
                      "de": "Position", "pt": "Cargo"},
    "term.member": {"en": "Member", "es": "Miembro", "fr": "Membre",
                    "de": "Mitglied", "pt": "Membro"},
    "term.context_brief": {"en": "Context brief", "es": "Resumen de contexto",
                           "fr": "Resume du contexte", "de": "Kontextuebersicht",
                           "pt": "Resumo de contexto"},
    "term.handoff_rules": {"en": "Handoff rules", "es": "Reglas de traspaso",
                           "fr": "Regles de transfert", "de": "Uebergaberegeln",
                           "pt": "Regras de transferencia"},
    "term.trust_level": {"en": "Trust level", "es": "Nivel de confianza",
                         "fr": "Niveau de confiance", "de": "Vertrauensstufe",
                         "pt": "Nivel de confianca"},
    "term.training_mode": {"en": "Training mode", "es": "Modo de entrenamiento",
                           "fr": "Mode formation", "de": "Trainingsmodus",
                           "pt": "Modo de treino"},
    "term.relationship_health": {"en": "Relationship health",
                                 "es": "Salud de la relacion",
                                 "fr": "Sante de la relation",
                                 "de": "Beziehungszustand",
                                 "pt": "Saude do relacionamento"},
    "term.calculated": {"en": "How this was calculated",
                        "es": "Como se calculo", "fr": "Comment ceci a ete calcule",
                        "de": "Wie dies berechnet wurde",
                        "pt": "Como isto foi calculado"},
}

# A character budget per key. A translation that outgrows it is the string that
# overflows its button; the number is a proxy for a rendering test that cannot
# run without screens, and the doc says so.
BUDGETS = {
    "nav.contacts": 24, "nav.companies": 24, "nav.deals": 20, "nav.activity": 22,
    "nav.history": 22, "nav.settings": 26, "action.save": 16, "action.cancel": 16,
    "action.delete": 18, "action.edit": 16, "action.new": 10, "action.close": 16,
    "action.next": 14, "action.back": 12, "search.placeholder": 28,
    "state.empty": 28, "state.loading": 18, "field.required": 18,
    "term.connected_system": 30, "term.workspace": 28, "term.position": 22,
    "term.member": 20, "term.context_brief": 30, "term.handoff_rules": 28,
    "term.trust_level": 26, "term.training_mode": 26, "term.relationship_health": 34,
    "term.calculated": 34,
}


class LocaleError(Exception):
    """Raised when a locale or a message key does not exist."""


def direction(code: str) -> str:
    return "rtl" if META.get(code, LocaleMeta(code, code)).rtl else "ltr"


class Translator:
    """Message lookup with a fallback, and no silent empty string."""

    def __init__(self, code: str = BASE_LOCALE, fallback: str = BASE_LOCALE):
        if code not in META:
            raise LocaleError(f"unknown locale {code!r}")
        self.code = code
        self.fallback = fallback

    def t(self, key: str) -> str:
        entry = CATALOGUE.get(key)
        if entry is None:
            raise LocaleError(f"unknown message key {key!r}")
        if self.code in entry:
            return entry[self.code]
        if self.fallback in entry:
            return entry[self.fallback]
        raise LocaleError(f"{key!r} has no {self.fallback} translation either")

    def has(self, key: str) -> bool:
        return key in CATALOGUE

    @property
    def rtl(self) -> bool:
        return direction(self.code) == "rtl"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_number(value: float, code: str = BASE_LOCALE, decimals: int = 0) -> str:
    meta = META.get(code) or META[BASE_LOCALE]
    formatted = f"{value:,.{decimals}f}"
    if meta.thousands_separator != ",":
        formatted = formatted.replace(",", "\x00")
    if meta.decimal_separator != ".":
        formatted = formatted.replace(".", meta.decimal_separator)
    return formatted.replace("\x00", meta.thousands_separator)


def format_currency(amount_minor: int, currency: str, code: str = BASE_LOCALE,
                    decimals: int = 2) -> str:
    """Amounts are stored in minor units. Formatting never changes the value."""
    value = amount_minor / 100.0
    return f"{format_number(value, code, decimals)} {currency}"


def format_date(moment: datetime, code: str = BASE_LOCALE, tz: str = "Asia/Kolkata") -> str:
    """A date in the user's timezone, in the locale's order.

    The timezone conversion is the part that matters: a deal that closes at 23:30
    in Kolkata is the 15th there and the 15th in UTC, but 20:00 in Kolkata on the
    14th is the 14th there and the 14th in UTC only by accident.
    """
    from datetime import timedelta

    local = _to_timezone(moment, tz)
    order = (META.get(code) or META[BASE_LOCALE]).date_order
    day, month, year = local.day, local.month, local.year
    if order == "DMY":
        return f"{day:02d}/{month:02d}/{year}"
    if order == "MDY":
        return f"{month:02d}/{day:02d}/{year}"
    return f"{year}-{month:02d}-{day:02d}"


def format_time(moment: datetime, tz: str = "Asia/Kolkata") -> str:
    local = _to_timezone(moment, tz)
    return f"{local.hour:02d}:{local.minute:02d}"


# A fixed-offset table. Real deployments need a tz database; this is enough to
# make the conversion real and the test meaningful, and the doc says which it is.
OFFSETS = {
    "Asia/Kolkata": 5.5, "UTC": 0.0, "Europe/London": 0.0, "Europe/Berlin": 1.0,
    "Europe/Madrid": 1.0, "Europe/Paris": 1.0, "Europe/Lisbon": 0.0,
    "America/New_York": -5.0,
}


def _to_timezone(moment: datetime, tz: str) -> datetime:
    from datetime import timedelta

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    offset = OFFSETS.get(tz)
    if offset is None:
        raise LocaleError(f"unknown timezone {tz!r}")
    return moment.astimezone(timezone(timedelta(hours=offset)))


# ---------------------------------------------------------------------------
# Currency conversion at the transaction date
# ---------------------------------------------------------------------------

@dataclass
class Rate:
    base: str
    quote: str
    rate: float
    effective_from: str       # ISO date, inclusive


class RateTable:
    """Historical rates, looked up on the transaction date.

    A rate is effective from its date until the next one for the same pair. A
    conversion dated before the first rate raises: inventing a rate is how a
    finance report becomes fiction.
    """

    def __init__(self, rates: list[Rate] | None = None):
        self.rates: list[Rate] = list(rates or [])

    def add(self, base: str, quote: str, rate: float, effective_from: str) -> Rate:
        if rate <= 0:
            raise LocaleError("a rate must be positive")
        entry = Rate(base.upper(), quote.upper(), rate, effective_from)
        self.rates.append(entry)
        self.rates.sort(key=lambda r: (r.base, r.quote, r.effective_from))
        return entry

    def rate_on(self, base: str, quote: str, on: str) -> float:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return 1.0
        candidates = [r for r in self.rates
                      if r.base == base and r.quote == quote and r.effective_from <= on]
        if not candidates:
            raise LocaleError(f"no {base}->{quote} rate effective on {on}")
        return candidates[-1].rate

    def convert(self, amount_minor: int, base: str, quote: str, on: str) -> int:
        """Convert in minor units, rounding half-up. Never at today's rate."""
        rate = self.rate_on(base, quote, on)
        return int(round(amount_minor * rate))


# ---------------------------------------------------------------------------
# The checks that can run without screens
# ---------------------------------------------------------------------------

def check_catalogue(locales: tuple[str, ...] = LOCALES) -> list[str]:
    """Every key, every locale, every budget. Returns problems, not a boolean."""
    problems = []
    for key, entry in CATALOGUE.items():
        for code in locales:
            if code not in entry:
                problems.append(f"{key}: no {code} translation")
        for code, text in entry.items():
            budget = BUDGETS.get(key)
            if budget and len(text) > budget:
                problems.append(
                    f"{key}[{code}]: {len(text)} characters exceeds the {budget} budget")
    for key in BUDGETS:
        if key not in CATALOGUE:
            problems.append(f"{key}: budget declared for a key that does not exist")
    return problems


def _swap(name: str, first: str, second: str) -> str | None:
    """Rename a token, preserving the case of the segment being replaced.

    The first version of this compared against lowercase literals, so
    `paddingLeft` and `paddingRight` both failed the test and were copied through
    unchanged - an RTL layout that silently stayed LTR. (R-14)
    """
    for a, b in ((first.capitalize(), second.capitalize()), (first, second)):
        if a in name:
            return name.replace(a, b)
    return None


def mirror(tokens: dict) -> dict:
    """Swap left and right in a token set, for an RTL layout.

    Only directional tokens are swapped. Mirroring everything is how a layout ends
    up with its icons backwards and its text right-aligned twice.
    """
    swapped = {}
    for name, value in tokens.items():
        target = (_swap(name, "left", "right")
                  or _swap(name, "right", "left")
                  or _swap(name, "start", "end")
                  or _swap(name, "end", "start")
                  or name)
        swapped[target] = value
    return swapped
