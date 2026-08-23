"""One-shot: fold the two downloaded règlements de la consultation into
samples/real_requirements.json, with provenance and the gaps they revealed.

Kept in the repository rather than run and deleted, because the provenance of
the quoted wording is the whole value of that file: anyone should be able to see
where each excerpt came from and re-derive it.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "samples" / "real_requirements.json"

ANTAI = {
    "id": "ANTAI_AOO_2026_06_TME",
    "buyer": "Ministère de l'Intérieur — ANTAI (Agence Nationale de Traitement Automatisé des Infractions)",
    "object": "Infogérance et service de support utilisateur pour les chaînes de traitement de l'ANTAI",
    "procedure": "appel d'offres ouvert",
    "cpv": "72250000",
    "deadline": "2026-10-28T12:00:00",
    "notice": "https://www.marches-publics.gouv.fr/entreprise/consultation/3044069",
    "local_file": "samples/real_dce/rc_ANTAI_2026.pdf",
    "_note": "The full règlement de la consultation, 34 pages, downloaded from PLACE. This is the document type the notices point at and never contain.",
    "excerpts": [
        {
            "section": "IV.6 1°",
            "page": 12,
            "text": "Une lettre de candidature par laquelle le candidat indique : […] Les noms, adresses, SIRET du / des entreprise(s) candidate(s) ; Le nom du représentant habilité à engager le candidat",
            "answered_by": "form",
            "note": "DC1 by another name. The form number is only given as a link, so an extractor keyed on 'DC1' would miss it here and catch it in the DGAC file — the same obligation, named two different ways."
        },
        {
            "section": "IV.6 2°",
            "page": 13,
            "text": "Une déclaration sur l'honneur pour justifier qu'il n'entre dans aucun des cas mentionnés aux articles L. 2141-1 à L. 2141-5 et L. 2141-7 à L. 2141-11 notamment qu'il satisfait aux obligations concernant l'emploi des travailleurs handicapés définies aux articles L. 5212-1 à L. 5212-11 du code du travail",
            "answered_by": "declaration",
            "note": "TRANSCRIBED BY EYE FROM THE RENDERED PAGE. No text extractor returns this sentence — see gap 'text stored as pictures' below. A mandatory document, and the bid is eliminated without it (IV.9)."
        },
        {
            "section": "IV.6 3°",
            "page": 13,
            "text": "Chiffre d'affaires global pour chacun des 3 derniers exercices ; Assurance pour risques professionnels ; Description synthétique des principales prestations de même nature réalisées notamment dans le secteur public sur les 3 dernières années ; Effectifs moyens annuels sur la dernière année.",
            "answered_by": "mixed",
            "note": "Four obligations in one bullet list, of three different kinds: a company fact, a document with an expiry date, a narrative, and another company fact with a different window (1 year, not 3)."
        },
        {
            "section": "IV.7 MINIMAUX REQUIS",
            "page": 13,
            "text": "ne retiendra que les candidats, seuls ou en groupement, dont le chiffre d'affaires du dernier exercice disponible est supérieur ou égal à 138 000 000 euros hors taxe.",
            "answered_by": "company_fact",
            "measure": "turnover",
            "minimum_eur": 138000000,
            "window_years": 1,
            "aggregation": "average",
            "strict": False,
            "note": "Validates capacity.py against a second buyer: one year rather than three, 'supérieur ou égal' rather than 'strictement supérieur', and a threshold two orders of magnitude larger. Nothing in the module needed changing."
        },
        {
            "section": "IV.8",
            "page": 13,
            "text": "Les candidats ne sont pas tenus de fournir ces justificatifs lorsque l'ANTAI peut les obtenir directement par le biais d'un système électronique de mise à disposition d'informations administré par un organisme officiel ou d'un espace de stockage numérique, à condition que figurent dans sa candidature toutes les informations nécessaires à la consultation de ce système ou de cet espace et que l'accès soit gratuit.",
            "answered_by": "not_required_conditionally",
            "note": "A document absent from the folder may be absent legitimately. MISSING is the wrong verdict here."
        },
        {
            "section": "IV.6 3° (closing paragraph)",
            "page": 13,
            "text": "Si, pour une raison justifiée, le candidat n'est pas en mesure de produire les renseignements et documents demandés par l'ANTAI, il est autorisé à prouver sa capacité économique et financière par tout autre moyen considéré comme approprié par l'ANTAI.",
            "answered_by": "alternative_path",
            "note": "The young-company escape route from 22-88307, generalised: any justified inability opens an alternative. Confirms NEEDS_REVIEW rather than MISSING as the default for unmet capacity requirements."
        },
        {
            "section": "IV.9",
            "page": 14,
            "text": "Les candidatures incomplètes ou demeurées incomplètes à la suite d'une demande de compléments sont éliminées.",
            "answered_by": "consequence",
            "note": "What the whole tool is aimed at. Note the two stages: the buyer may ask for completions first, so a gap found before submission costs nothing and a gap found after costs the bid."
        },
        {
            "section": "IV.10",
            "page": 14,
            "text": "Dans le cas d'une candidature d'un groupement d'opérateurs économiques, chaque membre du groupement doit fournir l'ensemble des documents et renseignements attestant de ses capacités juridiques, professionnelles, techniques et financières. L'appréciation des capacités du groupement est globale.",
            "answered_by": "cardinality",
            "note": "The document checklist multiplies by the number of members, while the capacity thresholds are assessed on the group as a whole. Two different rules in one paragraph."
        }
    ]
}

DGAC = {
    "id": "2026SDCRH05",
    "buyer": "Ministère des transports — Direction générale de l'aviation civile",
    "object": "Préparation aux épreuves écrites scientifiques des concours internes techniques des corps spécifiques de la DGAC",
    "procedure": "procédure adaptée (R2123-1 3°)",
    "deadline": "2026-09-11T12:00:00",
    "notice": "https://betterplace.info/files/3007789-reglement.pdf",
    "local_file": "samples/real_dce/rc_2026SDCRH05.pdf",
    "_note": "Not an IT tender. Kept because its PDF is cleanly extractable on all 14 pages, which makes it the negative control for tests/test_extraction.py — without a file that must NOT be flagged, the detector's thresholds would be untestable.",
    "excerpts": [
        {
            "section": "5.4 Présentation de la candidature",
            "page": 5,
            "text": "Lettre de candidature ou formulaire DC1 […] ou équivalent, dûment rempli, et daté. Dans le cas d'un groupement d'entreprises, le formulaire DC1 sera complété pour chaque membre du groupement",
            "answered_by": "form",
            "note": "'ou équivalent' — a third alternative on top of the two named ones."
        },
        {
            "section": "5.4",
            "page": 5,
            "text": "déclaration concernant le chiffre d'affaires global et le chiffre d'affaires concernant les prestations objet du marché, réalisés au cours des trois derniers exercices disponibles",
            "answered_by": "company_fact",
            "measure": "turnover",
            "window_years": 3,
            "note": "TWO turnover figures, not one: global, and the share relating to the subject of the contract. A profile carrying a single turnover series cannot answer this."
        },
        {
            "section": "5.4",
            "page": 6,
            "text": "Déclaration sur l'honneur précisant que le candidat n'est pas, au moment du dépôt de la candidature, en situation de redressement judiciaire, ou, à défaut, la copie du ou des jugements prononcés",
            "answered_by": "declaration",
            "note": "The 'à défaut' branch is not a fallback for a missing document — it is what you supply when the declaration would be false. Two paths chosen by the facts, not by convenience."
        },
        {
            "section": "6.1 Présentation de l'offre initiale",
            "page": 7,
            "text": "L'attestation de l'Administration fiscale en cas de non-assujettissement à la TVA pour les organismes de formation. […] le cas échéant le DC4",
            "answered_by": "conditional",
            "note": "Obligations that only apply under a condition. Reporting these as MISSING for a bidder they do not concern is noise, and noise is how a report stops being read."
        },
        {
            "section": "6.2 Examen des offres",
            "page": 7,
            "text": "l'acheteur peut autoriser tous les soumissionnaires concernés à régulariser les offres irrégulières dans un délai approprié",
            "answered_by": "consequence",
            "note": "Compare with 5.8, where an incomplete candidature is eliminated. The same missing paper carries a different penalty depending on which pile it belongs to."
        }
    ]
}

NEW_GAPS = [
    {
        "gap": "Some of the text is a picture of text.",
        "detail": "Page 13 of the ANTAI file reads '2° Une déclaration sur l'honneur pour justifier qu'il n'entre dans aucun des cas mentionnés aux articles L. 2141-1...' on screen. pypdf, pdfplumber and PyMuPDF all return '2°' followed by 'articles L. 2141-1 à L. 2141-5 et L. 2141-7 à L. 2141-'. Runs of text were rasterised into image strips and pasted back in place: ten of them on that page, 261 across the document. A mandatory document is therefore invisible to every extractor, and a checklist built on that text omits it while reporting nothing amiss.",
        "answer": "extraction.py — detects image blocks shaped like lines of text, names the pages, and forbids concluding that anything is absent from a file it could not read in full."
    },
    {
        "gap": "Candidature and offre are two piles with different penalties.",
        "detail": "An incomplete candidature is eliminated (ANTAI IV.9, DGAC 5.8). An irregular offer may be regularised (DGAC 6.2). The same missing paper is fatal in one pile and fixable in the other.",
        "answer": "Not built yet. Stage currently has BID and PERFORMANCE; BID needs splitting, and severity must follow the pile."
    },
    {
        "gap": "An obligation can be conditional.",
        "detail": "'L'attestation de l'Administration fiscale en cas de non-assujettissement à la TVA', 'le cas échéant le DC4', 'ou, à défaut, la copie du ou des jugements'. These do not apply to every bidder. Reporting them MISSING is noise, and noise is how a report stops being read.",
        "answer": "Not built yet. An obligation needs a predicate, and an inapplicable one needs a verdict distinct from both COVERED and MISSING."
    },
    {
        "gap": "The buyer may already hold the proof.",
        "detail": "ANTAI IV.8 and DGAC 5.5 both waive justificatifs the buyer can obtain free of charge from an official system. A document absent from the folder may be absent legitimately.",
        "answer": "Not built yet. Another reason MISSING must not be the default verdict for an unmatched obligation."
    },
    {
        "gap": "A group multiplies the checklist but not the thresholds.",
        "detail": "ANTAI IV.10: every member of a groupement supplies the full set of documents, while capacities are assessed on the group as a whole. Document rows scale with membership; capacity rows do not.",
        "answer": "Not built yet — recorded before writing obligations.py, which is the only moment it is free."
    },
    {
        "gap": "One requirement can demand two figures.",
        "detail": "DGAC 5.4 asks for global turnover AND the turnover relating to the subject of the contract, over the same three years. A profile holding one turnover series per year cannot answer it.",
        "answer": "Not built yet. capacity.Profile needs a second turnover series, or Measure needs a qualifier."
    }
]


def main() -> None:
    data = json.loads(TARGET.read_text(encoding="utf-8"))

    known = {source["id"] for source in data["sources"]}
    for source in (ANTAI, DGAC):
        if source["id"] in known:
            raise SystemExit(f"{source['id']} already recorded — nothing to do")
        data["sources"].append(source)

    recorded = {gap["gap"] for gap in data["design_gaps_this_material_revealed"]}
    for gap in NEW_GAPS:
        if gap["gap"] not in recorded:
            data["design_gaps_this_material_revealed"].append(gap)

    data["_a_note_on_availability"] = (
        "Since eForms became mandatory, notices no longer carry the participation "
        "conditions: they point at the consultation file instead. The 22-* excerpts "
        "below come from notices published under the previous national format, which "
        "stated them in full. The two 2026 entries are the consultation files "
        "themselves, downloaded from PLACE and committed under samples/real_dce/ — "
        "that is where this wording lives now."
    )

    TARGET.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(data['sources'])} sources, "
          f"{len(data['design_gaps_this_material_revealed'])} design gaps recorded")


if __name__ == "__main__":
    main()
