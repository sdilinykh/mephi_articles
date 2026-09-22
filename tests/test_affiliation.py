from src.parsers.affiliation import clean_affiliation, is_mephi_affiliation
from src.parsers.authors import author_match_key, clean_author_name, extract_author_orcids_from_html, extract_orcid, is_valid_author_name

def test_mephi_en():
    assert is_mephi_affiliation("NRNU MEPhI, Moscow, Russia")

def test_mephi_ru_with_curly_quotes():
    assert is_mephi_affiliation("Национальный исследовательский ядерный университет “МИФИ”")

def test_not_mephi():
    assert not is_mephi_affiliation("State Atomic Energy Corporation ROSATOM, Moscow, Russia")

def test_clean_affiliation_removes_numeric_label():
    assert clean_affiliation("1 Ivanovo State Power Engineering University, Ivanovo") == "Ivanovo State Power Engineering University, Ivanovo"

def test_clean_affiliation_keeps_organization_name_without_address():
    assert clean_affiliation("Beloyarsk NPP, POB 149, 624250 Zarechny, Sverdlovsk reg., Russia Beloyarsk NPP Zarechny Russia") == "Beloyarsk NPP"
    assert clean_affiliation("Bauman Moscow State Technical University, 5/1 2nd Baumanskaya Str., 105005 Moscow, Russia Bauman Moscow State Technical University Moscow Russia") == "Bauman Moscow State Technical University"
    assert clean_affiliation("State Atomic Energy Corporation ROSATOM, 24 Bolshaya Ordynka str., 119017 Moscow, Russia State Atomic Energy Corporation ROSATOM Moscow Russia") == "ROSATOM State Atomic Energy Corporation"
    assert clean_affiliation("AKME-Engineering JSC, 13 Bld. 1, Pyatnitskaya Str., 115035 Moscow, Russia AKME-Engineering JSC Moscow Russia") == "AKME-Engineering JSC"
    assert clean_affiliation("JSC Karpov Institute of Physical Chemistry, 6 Kievskoye shosse, 249033 Obninsk, Kaluga Reg., Russia") == "Karpov Institute of Physical Chemistry"
    assert clean_affiliation("JSC V.G. Khlopin Radium Institute, 28, 2nd Murinsky ave., St. Petersburg, 194021, Russia") == "V.G. Khlopin Radium Institute JSC"

def test_author_orcid_is_extracted_and_removed_from_name():
    value = "Ivan Ivanov 1 ORCID: 0000-0002-7181-4533"
    assert extract_orcid(value) == "0000-0002-7181-4533"
    assert clean_author_name(value) == "Ivan Ivanov"

def test_author_initials_first_matches_surname_first():
    assert clean_author_name("С. А. Полицын") == "Полицын, С. А."
    assert author_match_key("С. А. Полицын") == author_match_key("Полицын, С. А.")

def test_author_orcid_is_extracted_from_author_bio():
    html = """
    <div class="authorBio">
      <p><em>С. А. Полицын</em>
      <a href="http://orcid.org/0000-0002-0744-6035">ORCID</a></p>
    </div>
    """
    assert extract_author_orcids_from_html(html) == {"Полицын, С. А.": "0000-0002-0744-6035"}

def test_invalid_author_noise():
    assert not is_valid_author_name("101000")
    assert not is_valid_author_name("AAArtamonov@mephi.ru")
    assert not is_valid_author_name("Lasers and Equipment TM Group")
    assert not is_valid_author_name('SPC "Lasers and equipment TM" LLC')
