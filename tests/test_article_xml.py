from src.parsers.article import parse_article_xml


def test_article_xml_doi_and_funding():
    xml = """
    <article>
      <front>
        <article-meta>
          <article-id pub-id-type="doi">10.3897/nucet.11.168649</article-id>
          <title-group>
            <article-title>﻿Use of Americium and Curium fractions</article-title>
          </title-group>
        </article-meta>
      </front>
      <body>
        <sec sec-type="﻿Funding">
          <title>﻿Funding</title>
          <p>The work was carried out within the framework of funding of the National Research Nuclear University MEPhI by the Ministry of Education and Science of the Russian Federation.</p>
        </sec>
      </body>
    </article>
    """
    parsed = parse_article_xml(xml)

    assert parsed["doi"] == "10.3897/nucet.11.168649"
    assert parsed["title"] == "Use of Americium and Curium fractions"
    assert parsed["funding"]
