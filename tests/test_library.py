"""The fixture IS the demonstration, so it is tested like code.

Every verdict the tool can return has to fire against the sample library. A
matrix where everything is covered demonstrates nothing; one where everything
is broken demonstrates nothing either.

The point of these tests is not that the loader works. It is that **the demo
still works**. Change a date in `evidence_library.json` and the test names the
case you broke — which beats finding out while screen-recording.
"""

from datetime import date
from pathlib import Path

import pytest

from tender_compliance.library import LibraryError, load, missing_by_design
from tender_compliance.validity import Requirement, Validity, assess, days_of_slack

LIBRARY = Path(__file__).resolve().parent.parent / "samples" / "evidence_library.json"

# The day the sample was authored. Fixed rather than read from the clock: the
# EXPIRED case depends on "today", and a test that drifts with the calendar
# would start failing on its own one morning.
TODAY = date(2026, 8, 23)


@pytest.fixture(scope="module")
def library():
    documents, deadline = load(LIBRARY)
    return {doc.name: doc for doc in documents}, deadline


def test_the_library_loads_and_carries_its_deadline(library):
    documents, deadline = library
    assert len(documents) >= 10
    assert deadline == date(2026, 10, 9)


class TestEveryVerdictFires:
    """One document per verdict. Lose one and the demo loses a scene."""

    def test_the_money_shot_expires_before_the_deadline(self, library):
        documents, deadline = library
        doc = documents["Attestation d'assurance responsabilité civile professionnelle"]
        assert assess(doc, deadline, today=TODAY) is Validity.EXPIRES_BEFORE_DEADLINE
        # Nine days. The number is what makes it a phone call rather than a
        # renewal to start today — a status alone does not carry that.
        assert days_of_slack(doc, deadline) == -9

    def test_a_perfectly_valid_document_is_refused_for_its_age(self, library):
        documents, deadline = library
        doc = documents["Attestation de vigilance URSSAF"]
        assert assess(doc, deadline, today=TODAY) is Validity.VALID
        assert (
            assess(doc, deadline, today=TODAY, requirement=Requirement(max_age_months=6))
            is Validity.TOO_OLD
        )

    def test_one_certificate_has_already_lapsed(self, library):
        documents, deadline = library
        doc = documents["Certificat ISO/IEC 27001"]
        assert assess(doc, deadline, today=TODAY) is Validity.EXPIRED

    def test_one_document_has_a_date_nobody_could_read(self, library):
        documents, deadline = library
        doc = documents["Label ExpertCyber"]
        assert assess(doc, deadline, today=TODAY) is Validity.UNKNOWN

    def test_and_most_of_the_folder_is_fine(self, library):
        # A report that flags everything is a report nobody reads twice.
        documents, deadline = library
        verdicts = [assess(doc, deadline, today=TODAY) for doc in documents.values()]
        assert verdicts.count(Validity.VALID) >= len(verdicts) // 2


def test_some_requirements_cannot_be_answered_at_all(library):
    # The MISSING rows. Without them the matrix has no gap to point at.
    absent = missing_by_design(LIBRARY)
    assert absent
    assert all(isinstance(name, str) and name for name in absent)


class TestLoadingRefusesWhatItCannotTrust:
    """A library read with a shrug produces a matrix that looks complete."""

    def test_a_library_without_a_deadline_is_refused(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text('{"documents": [{"name": "x"}]}', encoding="utf-8")
        with pytest.raises(LibraryError, match="reference_deadline"):
            load(path)

    def test_an_empty_library_is_refused(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text('{"reference_deadline": "2026-10-09", "documents": []}', encoding="utf-8")
        with pytest.raises(LibraryError, match="no documents"):
            load(path)

    def test_a_malformed_date_names_the_document(self, tmp_path):
        # "the library is invalid" sends someone through 40 entries by hand.
        path = tmp_path / "library.json"
        path.write_text(
            '{"reference_deadline": "2026-10-09",'
            ' "documents": [{"name": "Assurance RC", "expires_on": "30/09/2026"}]}',
            encoding="utf-8",
        )
        with pytest.raises(LibraryError, match="Assurance RC"):
            load(path)

    def test_a_document_without_a_name_is_refused(self, tmp_path):
        path = tmp_path / "library.json"
        path.write_text(
            '{"reference_deadline": "2026-10-09", "documents": [{"expires_on": null}]}',
            encoding="utf-8",
        )
        with pytest.raises(LibraryError, match="no name"):
            load(path)


def test_a_forgotten_expiry_field_becomes_unknown_not_valid(tmp_path):
    """The rule that justifies the loader existing.

    Someone filling in a library and not thinking about expiry must not get a
    silent pass. An oversight becomes a line to check, not a green tick.
    """
    path = tmp_path / "library.json"
    path.write_text(
        '{"reference_deadline": "2026-10-09",'
        ' "documents": [{"name": "Assurance RC"}]}',
        encoding="utf-8",
    )
    documents, deadline = load(path)
    assert assess(documents[0], deadline, today=TODAY) is Validity.UNKNOWN


def test_the_sample_says_it_is_fictional(tmp_path):
    # A demonstration built on a fabricated compliance file must say so. A
    # reader who discovers an undisclosed fabrication is right to doubt the
    # rest of the report.
    import json

    raw = json.loads(LIBRARY.read_text(encoding="utf-8"))
    assert raw.get("fictional") is True
    readme = (LIBRARY.parent / "README.md").read_text(encoding="utf-8")
    assert "fabricated" in readme.lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
