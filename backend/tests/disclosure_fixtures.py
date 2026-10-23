"""공시 파이프라인 테스트 공용 도구 (작은 XML·가짜 토크나이저)."""

import io
import re
import zipfile

from pipelines.common.config import load_config

CONFIG = load_config("configs/common.yaml")
EXCLUDE_PATTERNS = CONFIG["parse"]["exclude_title_patterns"]

SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT>
<DOCUMENT-NAME ACODE="11012">반기보고서</DOCUMENT-NAME>
<COMPANY-NAME AREGCIK="00126380">삼성전자주식회사</COMPANY-NAME>
<BODY>
<COVER>
<P>표지 문구</P>
<TABLE><TBODY><TR>
<TD>사업연도</TD><TU AUNIT="PERIODFROM" AUNITVALUE="20260101">2026년 01월 01일</TU>
<TU AUNIT="PERIODTO" AUNITVALUE="20260630">2026년 06월 30일</TU>
</TR></TBODY></TABLE>
</COVER>
<SECTION-1><TITLE>【 대표이사 등의 확인 】</TITLE><P>확인서 본문</P></SECTION-1>
<SECTION-1><TITLE>I. 회사의 개요</TITLE>
<SECTION-2><TITLE>1. 회사의   개요</TITLE>
<P>첫 문단입니다.</P>
<P></P>
<PGBRK></PGBRK>
<P>둘째 <SPAN>문단</SPAN>입니다.</P>
<P HIDDEN="Y">숨김 문단</P>
</SECTION-2>
</SECTION-1>
<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE>
<LIBRARY>
<SECTION-2><TITLE>2. 연결재무제표</TITLE>
<TABLE-GROUP><TITLE>2-1. 연결 재무상태표</TITLE>
<TABLE><TBODY>
<TR><TE>연결 재무상태표</TE></TR>
<TR><TE>(단위 : 백만원)</TE></TR>
</TBODY></TABLE>
<TABLE>
<THEAD>
<TR><TH ROWSPAN="2">과목</TH><TH COLSPAN="2">당기</TH></TR>
<TR><TH>3개월</TH><TH>누적</TH></TR>
</THEAD>
<TBODY>
<TR><TE ROWSPAN="2">자산</TE><TE>10</TE><TE>20</TE></TR>
<TR><TE>30</TE><TE>40</TE></TR>
<TR><TE COLSPAN="2">합계</TE><TE>60</TE></TR>
</TBODY>
</TABLE>
</TABLE-GROUP>
</SECTION-2>
<SECTION-2><TITLE>3. 연결재무제표 주석</TITLE>
<TABLE-GROUP><TITLE>5. 재고자산 (연결)</TITLE>
<TABLE><TBODY><TR><TD>
<P>재고자산의 내역은 다음과 같습니다.</P>
<TABLE><TBODY>
<TR><TE>당반기말</TE><TE>(단위 : 백만원)</TE></TR>
</TBODY></TABLE>
<TABLE>
<THEAD><TR><TH>구분</TH><TH>금액</TH></TR></THEAD>
<TBODY><TR><TE>제품</TE><TE>100</TE></TR></TBODY>
</TABLE>
</TD></TR></TBODY></TABLE>
</TABLE-GROUP>
<TABLE-GROUP><TITLE>6. 재고자산 (별도)</TITLE><P>별도 주석</P></TABLE-GROUP>
</SECTION-2>
<SECTION-2><TITLE>4. 재무제표</TITLE><P>별도 본표</P></SECTION-2>
<SECTION-2><TITLE>5. 재무제표 주석</TITLE><P>별도 주석 본문</P></SECTION-2>
</LIBRARY>
</SECTION-1>
</BODY>
</DOCUMENT>
"""


def zip_bytes(name: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content.encode("utf-8"))
    return buffer.getvalue()


class FakeTokens:
    """공백 단위 토큰 = 1토큰. offsets는 각 토큰의 문자 범위."""

    _TOKEN = re.compile(r"\S+")

    def count(self, text: str) -> int:
        return len(self._TOKEN.findall(text))

    def offsets(self, text: str) -> list[tuple[int, int]]:
        return [match.span() for match in self._TOKEN.finditer(text)]
