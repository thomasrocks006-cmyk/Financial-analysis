"""
TranscriptParserService — LLM-assisted transcript parsing.
Converts raw transcript text into structured ParsedTranscript with tagged guidance.
"""
import logging
import re
from research_pipeline.schemas.qualitative import ParsedTranscript, GuidanceStatement, ManagementToneSignal

logger = logging.getLogger(__name__)

# Heuristic patterns for guidance extraction
GUIDANCE_PATTERNS = [
    (r"(?:expect|guide|guidance|forecast|anticipate)\s+(?:EPS|earnings per share|revenue|sales|capex|capital expenditure)[^\n.]{0,100}", "guidance"),
    (r"(?:raised?|raising|increasing|higher)\s+(?:guidance|outlook|forecast)", "raise"),
    (r"(?:lowered?|lowering|reducing|below)\s+(?:guidance|expectations|consensus)", "lower"),
    (r"(?:reiterate|reaffirm|maintaining|unchanged)\s+(?:guidance|outlook)", "maintain"),
]

CAPEX_PATTERNS = [
    r"(?:capex|capital expenditure|capital spending)[^\n.]{0,150}",
    r"(?:billion|million)\s+(?:in|for)\s+(?:capex|infrastructure|data center)[^\n.]{0,100}",
    r"(?:invest|spend)\s+\$[0-9]+[^\n.]{0,100}(?:data center|GPU|AI infrastructure)[^\n.]{0,50}",
]

DEMAND_PATTERNS = [
    r"(?:demand|pipeline|backlog|order)[^\n.]{0,150}",
    r"(?:growing|strong|robust|accelerating)\s+(?:demand|interest)[^\n.]{0,100}",
]


class TranscriptParserService:
    """
    Heuristic + LLM-assisted transcript parser.
    Returns ParsedTranscript with structured guidance, capex, demand commentary.
    Cached by (ticker, quarter) to avoid re-parsing.
    """

    def __init__(self) -> None:
        self._cache: dict[str, ParsedTranscript] = {}

    async def parse(self, ticker: str, quarter: str, raw_text: str) -> ParsedTranscript:
        """Parse raw transcript text into structured ParsedTranscript using heuristic patterns."""
        cache_key = f"{ticker}:{quarter}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not raw_text:
            result = ParsedTranscript(ticker=ticker, quarter=quarter, parse_confidence=0.0)
            self._cache[cache_key] = result
            return result

        word_count = len(raw_text.split())
        guidance_statements: list[GuidanceStatement] = []
        capex_commentary: list[str] = []
        demand_commentary: list[str] = []
        margin_commentary: list[str] = []
        tone_signals: list[ManagementToneSignal] = []

        # Extract guidance statements
        for pattern, category in GUIDANCE_PATTERNS:
            for match in re.finditer(pattern, raw_text, re.IGNORECASE):
                text = match.group(0).strip()[:300]
                if len(text) > 30:
                    guidance_statements.append(GuidanceStatement(
                        category="other",
                        raw_text=text,
                        quarter=quarter,
                        confidence="implied",
                    ))

        # Extract capex commentary
        for pattern in CAPEX_PATTERNS:
            for match in re.finditer(pattern, raw_text, re.IGNORECASE):
                text = match.group(0).strip()[:300]
                if len(text) > 30 and text not in capex_commentary:
                    capex_commentary.append(text)

        # Extract demand commentary
        for pattern in DEMAND_PATTERNS:
            for match in re.finditer(pattern, raw_text, re.IGNORECASE):
                text = match.group(0).strip()[:200]
                if len(text) > 30 and text not in demand_commentary:
                    demand_commentary.append(text)

        # Simple tone detection
        positive_words = ["strong", "growing", "accelerating", "robust", "exceeding", "beat", "outperform"]
        negative_words = ["challenging", "headwind", "slowdown", "miss", "below", "concern", "uncertain"]
        text_lower = raw_text.lower()
        pos_count = sum(text_lower.count(w) for w in positive_words)
        neg_count = sum(text_lower.count(w) for w in negative_words)
        if pos_count > neg_count * 1.5:
            tone = "positive"
        elif neg_count > pos_count * 1.5:
            tone = "cautious"
        else:
            tone = "neutral"
        tone_signals.append(ManagementToneSignal(
            topic="overall",
            tone=tone,
            evidence_quote=raw_text[:100],
        ))

        parse_confidence = min(0.9, 0.3 + 0.1 * len(guidance_statements) + 0.05 * len(capex_commentary))

        result = ParsedTranscript(
            ticker=ticker,
            quarter=quarter,
            guidance_statements=guidance_statements[:10],
            capex_commentary=capex_commentary[:5],
            demand_commentary=demand_commentary[:5],
            margin_commentary=margin_commentary[:5],
            tone_signals=tone_signals,
            raw_word_count=word_count,
            parse_confidence=parse_confidence,
        )
        self._cache[cache_key] = result
        return result
