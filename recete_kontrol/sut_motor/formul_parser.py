# -*- coding: utf-8 -*-
"""Boolean formül parser — string → JSON formül ağacı.

Girdi: "(A1 ∨ A2) ∧ ¬B1 ∧ C1"
Çıktı: {"tip": "AND", "alt": [
            {"tip": "OR", "alt": [{"atom_ref": "A1"}, {"atom_ref": "A2"}]},
            {"atom_ref": "B1", "negatif": True},
            {"atom_ref": "C1"}
        ]}

Operatörler:
    AND: ∧, AND, &&, &, VE
    OR : ∨, OR, ||, |, VEYA
    NOT: ¬, NOT, !, DEGIL, DEĞİL (prefix unary)
    (, )

Atom referansı: harf ile başlayan + harf/rakam/tire/alt-tire devam eden token
                (A1, B-2, D1_alt, Y-3a, ...)

Hata: ParserHatasi(mesaj, konum). Konum 0-bazlı karakter indeksi.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class ParserHatasi(Exception):
    """Boolean formül parse hatası."""

    def __init__(self, mesaj: str, konum: int, kaynak: str = ""):
        self.konum = konum
        self.kaynak = kaynak
        super().__init__(self._formatla(mesaj))

    def _formatla(self, mesaj: str) -> str:
        if not self.kaynak:
            return f"[konum {self.konum}] {mesaj}"
        # Konumun etrafından 30 karakter göster
        bas = max(0, self.konum - 15)
        son = min(len(self.kaynak), self.konum + 15)
        snippet = self.kaynak[bas:son]
        isaret = ' ' * (self.konum - bas) + '^'
        return (f"[konum {self.konum}] {mesaj}\n"
                f"  ...{snippet}...\n"
                f"     {isaret}")


# ─────────────────────────────────────────────────────────────────────────
# Tokenizer
# ─────────────────────────────────────────────────────────────────────────

# Token tipleri
T_AND = 'AND'
T_OR = 'OR'
T_NOT = 'NOT'
T_LPAR = 'LPAR'
T_RPAR = 'RPAR'
T_ATOM = 'ATOM'
T_EOF = 'EOF'

# Çok-karakterli operatör eşleşmeleri (uzun olan önce — & match etmesin önce &&)
_COKLU_OP = [
    ('&&', T_AND), ('||', T_OR),
    ('AND', T_AND), ('OR', T_OR), ('NOT', T_NOT),
    ('VEYA', T_OR), ('DEGIL', T_NOT), ('DEĞİL', T_NOT),
    ('VE', T_AND),   # 'VE' kısa, atom isminde olamaz çünkü atom harf-rakam
]
# Tek karakter eşleşmeleri
_TEK_OP = {
    '∧': T_AND, '∨': T_OR, '¬': T_NOT,
    '&': T_AND, '|': T_OR, '!': T_NOT,
    '(': T_LPAR, ')': T_RPAR,
}


@dataclass
class Token:
    tip: str
    deger: str
    konum: int


def tokenize(kaynak: str) -> List[Token]:
    """Girdi string'i token listesine çevir."""
    tokens: List[Token] = []
    i = 0
    n = len(kaynak)
    while i < n:
        ch = kaynak[i]
        # Boşluk geç
        if ch.isspace():
            i += 1
            continue
        # Tek karakterli op
        if ch in _TEK_OP:
            tokens.append(Token(_TEK_OP[ch], ch, i))
            i += 1
            continue
        # Çok karakterli op (büyük/küçük harf duyarsız)
        eslesti = False
        for op_str, op_tip in _COKLU_OP:
            n_op = len(op_str)
            if i + n_op <= n and kaynak[i:i + n_op].upper() == op_str.upper():
                # Operatör sonrası harf/rakam değilse (yoksa atom adının
                # başlangıcı olabilir — "AND1" gibi)
                sonraki = kaynak[i + n_op] if i + n_op < n else ' '
                if not (sonraki.isalnum() or sonraki in '_-'):
                    tokens.append(Token(op_tip, op_str, i))
                    i += n_op
                    eslesti = True
                    break
        if eslesti:
            continue
        # Atom referansı (harf ile başlar)
        if ch.isalpha() or ch == '_':
            j = i + 1
            while j < n and (kaynak[j].isalnum() or kaynak[j] in '_-'):
                j += 1
            atom_adi = kaynak[i:j]
            tokens.append(Token(T_ATOM, atom_adi, i))
            i = j
            continue
        # Bilinmeyen karakter
        raise ParserHatasi(f"Beklenmeyen karakter: {ch!r}", i, kaynak)
    tokens.append(Token(T_EOF, '', n))
    return tokens


# ─────────────────────────────────────────────────────────────────────────
# Parser (recursive descent)
# ─────────────────────────────────────────────────────────────────────────
#
# Dilbilgisi (öncelik düşükten yükseğe):
#   formul   := or_ifade
#   or_ifade := and_ifade (OR and_ifade)*
#   and_ifade := not_ifade (AND not_ifade)*
#   not_ifade := NOT not_ifade | atom_ifade
#   atom_ifade := ATOM | LPAR or_ifade RPAR


class _Parser:
    def __init__(self, tokens: List[Token], kaynak: str):
        self.tokens = tokens
        self.kaynak = kaynak
        self.i = 0

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _ilerle(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _tuket(self, beklenen_tip: str) -> Token:
        tok = self._peek()
        if tok.tip != beklenen_tip:
            raise ParserHatasi(
                f"{beklenen_tip} bekleniyordu, {tok.tip} ({tok.deger!r}) bulundu",
                tok.konum, self.kaynak)
        return self._ilerle()

    def parse(self) -> Dict[str, Any]:
        agac = self._or_ifade()
        if self._peek().tip != T_EOF:
            tok = self._peek()
            raise ParserHatasi(
                f"Beklenmedik token: {tok.tip} ({tok.deger!r})",
                tok.konum, self.kaynak)
        return agac

    def _or_ifade(self) -> Dict[str, Any]:
        sol = self._and_ifade()
        if self._peek().tip != T_OR:
            return sol
        alt = [sol]
        while self._peek().tip == T_OR:
            self._ilerle()
            alt.append(self._and_ifade())
        return {'tip': 'OR', 'alt': alt}

    def _and_ifade(self) -> Dict[str, Any]:
        sol = self._not_ifade()
        if self._peek().tip != T_AND:
            return sol
        alt = [sol]
        while self._peek().tip == T_AND:
            self._ilerle()
            alt.append(self._not_ifade())
        return {'tip': 'AND', 'alt': alt}

    def _not_ifade(self) -> Dict[str, Any]:
        if self._peek().tip == T_NOT:
            self._ilerle()
            ic = self._not_ifade()  # NOT(NOT(...)) destekli
            # Eğer iç atom_ref ise negatif=True olarak işaretle
            if 'atom_ref' in ic and 'tip' not in ic:
                ic_yeni = dict(ic)
                ic_yeni['negatif'] = not ic.get('negatif', False)
                return ic_yeni
            # AND/OR alt-ifadelerine NOT — özel düğüm
            return {'tip': 'NOT', 'alt': [ic]}
        return self._atom_ifade()

    def _atom_ifade(self) -> Dict[str, Any]:
        tok = self._peek()
        if tok.tip == T_LPAR:
            self._ilerle()
            ic = self._or_ifade()
            self._tuket(T_RPAR)
            return ic
        if tok.tip == T_ATOM:
            self._ilerle()
            return {'atom_ref': tok.deger}
        raise ParserHatasi(
            f"Atom ya da '(' bekleniyordu, {tok.tip} ({tok.deger!r}) bulundu",
            tok.konum, self.kaynak)


# ─────────────────────────────────────────────────────────────────────────
# Genel API
# ─────────────────────────────────────────────────────────────────────────


def parse_formul(kaynak: str) -> Dict[str, Any]:
    """Boolean formül string → JSON formül ağacı.

    >>> parse_formul("A1 ∧ ¬B1")
    {'tip': 'AND', 'alt': [{'atom_ref': 'A1'}, {'atom_ref': 'B1', 'negatif': True}]}

    >>> parse_formul("(A1 ∨ A2) ∧ B1")
    {'tip': 'AND', 'alt': [
        {'tip': 'OR', 'alt': [{'atom_ref': 'A1'}, {'atom_ref': 'A2'}]},
        {'atom_ref': 'B1'}]}
    """
    if not kaynak or not kaynak.strip():
        raise ParserHatasi("Boş formül", 0, kaynak)
    tokens = tokenize(kaynak)
    parser = _Parser(tokens, kaynak)
    return parser.parse()


def kullanilan_atomlar(agac: Dict[str, Any]) -> set:
    """Formül ağacındaki tüm atom_ref'leri toplar — doğrulama için."""
    sonuc = set()

    def _yur(d: Dict):
        if 'atom_ref' in d:
            sonuc.add(d['atom_ref'])
        for alt in d.get('alt', []):
            _yur(alt)
    _yur(agac)
    return sonuc


# CLI smoke test (python -m sut_motor.formul_parser "...")
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python -m sut_motor.formul_parser \"A1 ∧ ¬B1\"")
        sys.exit(1)
    formul = sys.argv[1]
    try:
        agac = parse_formul(formul)
        import json
        print(json.dumps(agac, indent=2, ensure_ascii=False))
        print("Atomlar:", sorted(kullanilan_atomlar(agac)))
    except ParserHatasi as e:
        print(f"HATA: {e}")
        sys.exit(2)
