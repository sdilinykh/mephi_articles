from src.parsers.funding import extract_funding, extract_funding_from_html, extract_funding_from_sections, funding_section_found_in_html

def test_rfbr_example():
    text = "The reported study was funded by RFBR according to the research project 19-29-02006."
    hits = extract_funding(text)
    assert hits
    assert hits[0].funder_normalized == "RFBR"
    assert hits[0].grant_number == "19-29-02006"

def test_rsf_example():
    text = "This work was supported by the Russian Science Foundation, grant No. 24-12-00123."
    hits = extract_funding(text)
    assert hits
    assert hits[0].funder_normalized == "RSF"
    assert hits[0].grant_number == "24-12-00123"

def test_number_marker_inside_funder_name_is_not_treated_as_grant_number():
    text = "The work was supported by the Russian Science Foundation under grant No. 19-11-110082."
    hits = extract_funding(text)
    assert hits
    assert hits[0].funder_normalized == "RSF"
    assert hits[0].grant_number == "19-11-110082"

def test_number_after_a_footnote_marker_is_extracted():
    text = "The reported study was funded by the Russian Science Foundation (RSF) according to the research project ¹ 19-11-110082."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number == "19-11-110082"

def test_number_without_a_label_after_funder_is_extracted():
    text = "This work was supported by the Russian Foundation for Basic Research 23-19-0096."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number == "23-19-0096"

def test_contract_number_with_a_footnote_marker_is_extracted():
    text = "This work was supported by the Ministry of Education and Science of the Russian Federation (contract ¹ 14.604.21.0178)."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number == "14.604.21.0178"

def test_date_range_is_not_treated_as_an_unlabelled_grant_number():
    text = "This work was supported by Priority 2030 in 2022-2024."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number is None

def test_short_numeric_prefix_of_an_alphanumeric_code_is_not_a_grant_number():
    text = "This work was supported by Rosatom under Contract No. N.4o.241.19.20.1027."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number is None

def test_one_separator_number_immediately_after_funder_is_extracted():
    text = "This work was supported by RSF 24-2300111."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number == "24-2300111"

def test_number_is_extracted_only_from_acknowledgements_section():
    html = """
    <h2>Acknowledgements</h2>
    <p>The work was supported by the Russian Science Foundation under grant No. 19-11-110082.</p>
    """
    hits = extract_funding_from_html(html)
    assert hits
    assert hits[0].grant_number == "19-11-110082"

def test_grant_number_contains_only_digits_and_separators():
    text = "The work was supported by RFBR, grant No. ABC-19-11-110082."
    hits = extract_funding(text)
    assert hits
    assert hits[0].grant_number is None

def test_support_outside_section_is_not_counted_as_article_funding():
    text = "Introduction. This work was supported by RFBR according to project 19-29-02006."
    assert extract_funding_from_sections(text) == []

def test_empty_acknowledgements_are_not_funding_section():
    html = "<h2>Acknowledgements</h2><p>The authors thank anonymous reviewers.</p>"
    assert not funding_section_found_in_html(html)
    assert extract_funding_from_html(html) == []

def test_equipment_acknowledgement_marks_section_without_grant_number():
    html = """
    <h2>Acknowledgements</h2>
    <p>Measurements were performed using equipment of the National Research Center Kurchatov Institute.</p>
    """
    assert funding_section_found_in_html(html)
    hits = extract_funding_from_html(html)
    assert hits
    assert hits[0].funder_normalized == "NRC Kurchatov Institute"
    assert hits[0].grant_number is None
