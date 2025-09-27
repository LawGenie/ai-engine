from typing import List, Optional
import os

class KeywordExtractor:
    """경량 휴리스틱 키워드 추출기 (기본 폴백)."""

    def extract(self, product_name: str, product_description: str | None = None, top_k: int = 3) -> List[str]:
        text = f"{product_name or ''} {product_description or ''}".strip()
        ascii_text = ''.join(ch if (ord(ch) < 128 and (ch.isalnum() or ch.isspace())) else ' ' for ch in text)
        tokens = [t.lower() for t in ascii_text.split()]
        stop = {"the","a","an","and","or","for","with","of","in","to","on","by","from","into","how","are","is","be","us","u.s.","usa","guide","overview","products","product"}
        candidates = [t for t in tokens if t not in stop and len(t) >= 3]
        if not candidates and ("세럼" in text or "화장품" in text):
            candidates = ["cosmetic", "serum"]
        return candidates[:top_k]


class HfKeywordExtractor(KeywordExtractor):
    """Hugging Face 기반 키워드 추출 (간단 구현: 문장 임베딩 + 후보 랭킹).
    - 외부 후보가 없으므로 토큰을 후보로 간주하고 길이/빈도 기반 보정
    - 필요 시 keyBERT/KeyphraseVectorizers로 확장 가능
    """

    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        except Exception:
            self.model = None

    def extract(self, product_name: str, product_description: str | None = None, top_k: int = 3) -> List[str]:
        base = super().extract(product_name, product_description, top_k=20)
        if not self.model or not base:
            return base[:top_k]
        # 간단 랭킹: 길이 가중치 + 중복 제거
        unique = []
        seen = set()
        for t in base:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        # 길이 점수
        unique.sort(key=lambda x: (len(x) >= 4, len(x)), reverse=True)
        return unique[:top_k]


class OpenAiKeywordExtractor(KeywordExtractor):
    """OpenAI 기반 키워드 추출기 (선택 사용). 환경변수 USE_OPENAI_KEYWORDS=true 일 때만 사용."""

    def __init__(self):
        try:
            from openai import OpenAI
            self._OpenAI = OpenAI
        except Exception:
            self._OpenAI = None

    def extract(self, product_name: str, product_description: str | None = None, top_k: int = 3) -> List[str]:
        if not os.getenv("USE_OPENAI_KEYWORDS", "").lower() in ("1","true","yes"):
            return super().extract(product_name, product_description, top_k)
        if not self._OpenAI:
            return super().extract(product_name, product_description, top_k)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return super().extract(product_name, product_description, top_k)
        try:
            client = self._OpenAI(api_key=api_key)
            text = (product_name or "") + "\n" + (product_description or "")
            prompt = (
                "You are a domain keyword extractor for trade/import compliance. "
                "Return ONLY a JSON array of up to 3 short English keywords.\n" \
                f"TEXT:\n{text}\n"
            )
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_KEYWORDS_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "Extract core keywords for regulatory search."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=64
            )
            content = resp.choices[0].message.content.strip()
            import json
            kws = json.loads(content)
            if isinstance(kws, list):
                return [str(k)[:32] for k in kws][:top_k]
        except Exception:
            pass
        return super().extract(product_name, product_description, top_k)


