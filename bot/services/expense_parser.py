"""
Refined expense parser with better accuracy, multi-expense support, and income detection
"""
import re
from typing import Dict, Optional, List, Tuple, Sequence

class ExpenseParser:
    """
    Intelligent expense parser with:
    - Strict confidence scoring (fixes test failures)
    - Multi-expense support ("45k taxi, 15k snacks")
    - Income/expense detection
    """

    def __init__(self,):
        # Compile regex patterns once for performance
        self.amount_pattern = re.compile(
            r'(?:^|\s|,)(\d+(?:[.,]\d+)?)\s*(?:k|к|thousand|тысяч|т|thous)?(?:\s|,|$)',
            re.IGNORECASE
        )

        # Currency symbols (for dollar signs, etc.)
        self.currency_pattern = re.compile(r'[$€£₽]\s*(\d+(?:[.,]\d+)?)')

        # More strict category keywords with primary/secondary separation
        self.category_keywords = {
            'food': {
                'primary': ['lunch', 'dinner', 'breakfast', 'cafe', 'restaurant',
                            'eat', 'ate', 'eating', 'pizza', 'burger', 'sushi', 'coffee',
                            'обед', 'ужин', 'завтрак', 'кафе', 'еда', 'кофе', 'meal'],
                'secondary': ['snack', 'food'],
                'weight': 2.0
            },
            'transport': {
                'primary': ['taxi', 'uber', 'yandex', 'bus', 'metro', 'subway',
                            'такси', 'метро', 'автобус', 'яндекс', 'ride'],
                'secondary': ['fuel', 'gas', 'petrol', 'parking', 'бензин', 'паркинг'],
                'weight': 2.0
            },
            'groceries': {
                'primary': ['grocery', 'groceries', 'market', 'supermarket',
                            'магазин', 'продукты', 'makro', 'korzinka', 'havas'],
                'secondary': ['store', 'shop'],
                'weight': 1.8
            },
            'entertainment': {
                'primary': ['movie', 'cinema', 'film', 'game', 'concert',
                            'кино', 'игра', 'концерт'],
                'secondary': ['party', 'bar', 'club', 'theater'],
                'weight': 1.5
            },
            'shopping': {
                'primary': ['shopping', 'clothes', 'shoes', 'bought',
                            'одежда', 'обувь', 'купил'],
                'secondary': ['buy', 'shirt', 'pants', 'dress', 'покупка'],
                'weight': 1.2
            },
            'bills': {
                'primary': ['electricity', 'water', 'internet', 'phone', 'rent',
                            'электричество', 'вода', 'интернет', 'телефон', 'аренда'],
                'secondary': ['utility', 'bill', 'коммуналка'],
                'weight': 1.8
            },
            'healthcare': {
                'primary': ['doctor', 'hospital', 'pharmacy', 'medicine', 'pills',
                            'врач', 'больница', 'аптека', 'лекарство'],
                'secondary': ['clinic', 'dental', 'health'],
                'weight': 1.5
            },
        }

        # Income indicators (strong signals)
        self.income_indicators = {
            'strong': ['received', 'gift', 'got paid', 'earned', 'salary', 'income', 'paycheck',
                       'получил', 'зарплата', 'доход', 'оплата получена'],
            'weak': ['got', 'получил деньги']
        }

        # Expense indicators
        self.expense_indicators = {
            'strong': ['spent', 'paid', 'bought', 'purchased', 'cost',
                       'потратил', 'заплатил', 'купил', 'стоило'],
            'weak': ['for', 'on']
        }

    async def parse(
            self,
            text: str,
            user_id: int,
            user_categories: Optional[Sequence] = None
    ) -> Dict:
        """
        Parse expense/income from text

        Handles:
        - Single: "50k taxi"
        - Multiple: "45k taxi, 15k snacks, 30k coffee"
        - Income: "received 5k salary"
        """
        text = text.strip()

        # Check for multiple transactions (comma-separated)
        if ',' in text and self._has_multiple_expenses(text):
            return await self._parse_multiple(text, user_id, user_categories)

        # Single transaction
        return await self._parse_single(text, user_id, user_categories)

    def _has_multiple_expenses(self, text: str) -> bool:
        """Check if text contains multiple expenses"""
        # Count amounts in text
        amounts = self.amount_pattern.findall(text)
        currency_amounts = self.currency_pattern.findall(text)

        total_amounts = len(amounts) + len(currency_amounts)

        return total_amounts >= 2 and ',' in text

    async def _parse_multiple(
            self,
            text: str,
            user_id: int,
            user_categories: Optional[List] = None
    ) -> Dict:
        """
        Parse multiple expenses from comma-separated text

        Example: "45k taxi, 15k snacks, 30k coffee"
        """
        parts = [p.strip() for p in text.split(',')]
        transactions = []

        for part in parts:
            if not part:
                continue

            result = await self._parse_single(part, user_id, user_categories)

            if result.get('amount'):  # Only add if valid
                transactions.append({
                    'amount': result['amount'],
                    'category': result.get('category'),
                    'description': result.get('description', ''),
                    'confidence': result.get('confidence', 0.5),
                    'type': result.get('type', 'expense'),
                })

        if not transactions:
            # Failed to parse any - return single parse attempt
            return await self._parse_single(text, user_id, user_categories)

        return {
            'is_multiple': True,
            'transactions': transactions,
            'count': len(transactions),
            'confidence': sum(t['confidence'] for t in transactions) / len(transactions),
            'method': 'multi_parse'
        }

    async def _parse_single(
            self,
            text: str,
            user_id: int,
            user_categories: Optional[List] = None
    ) -> Dict:
        """Parse single transaction"""

        # Detect transaction type FIRST (income vs expense)
        transaction_type, type_confidence = self._detect_transaction_type(text)

        # Fast path: Try rule-based parsing
        result = self._parse_with_rules(text, user_categories)
        result['type'] = transaction_type
        result['type_confidence'] = type_confidence

        # Adjust confidence based on type detection
        if type_confidence < 0.7:
            result['confidence'] *= 0.9  # Slight penalty for unclear type

        # Mark if needs clarification
        if result['confidence'] < 0.5:
            result['needs_clarification'] = True

        return result

    def _detect_transaction_type(self, text: str) -> Tuple[str, float]:
        """
        Detect if this is income or expense

        Returns: (type, confidence)
        """
        text_lower = text.lower()

        # Check strong income indicators
        strong_income_score = sum(2 for indicator in self.income_indicators['strong']
                                  if indicator in text_lower)
        weak_income_score = sum(1 for indicator in self.income_indicators['weak']
                                if indicator in text_lower)

        # Check expense indicators
        strong_expense_score = sum(2 for indicator in self.expense_indicators['strong']
                                   if indicator in text_lower)
        weak_expense_score = sum(1 for indicator in self.expense_indicators['weak']
                                 if indicator in text_lower)

        income_score = strong_income_score + weak_income_score * 0.5
        expense_score = strong_expense_score + weak_expense_score * 0.5

        # Strong income signals
        if income_score > 0 and income_score > expense_score:
            confidence = min(0.95, 0.6 + income_score * 0.1)
            return 'income', confidence

        # Default to expense (most common)
        if expense_score > 0:
            confidence = min(0.9, 0.7 + expense_score * 0.1)
            return 'expense', confidence

        # No clear indicators - assume expense with low confidence
        return 'expense', 0.6

    def _parse_with_rules(
            self,
            text: str,
            user_categories: Optional[List] = None
    ) -> Dict:
        """
        Fast rule-based parsing with FIXED confidence scoring
        """
        text_lower = text.lower()

        # 1. Extract amount (try currency symbols first)
        amount, amount_confidence = self._extract_amount_improved(text_lower)

        # 2. Detect category with strict matching
        category, category_confidence, matched_keywords = self._detect_category_strict(
            text_lower,
            user_categories
        )

        # 3. Extract description
        description = self._extract_description(text, amount)

        # 4. Calculate STRICT overall confidence (FIXED)
        confidence = self._calculate_confidence_fixed(
            amount,
            amount_confidence,
            category,
            category_confidence,
            len(matched_keywords),
            text_lower
        )
        data = {
            'amount': amount,
            'category': category,
            'description': description,
            'confidence': confidence,
            'method': 'rule_based',
            'matched_keywords': matched_keywords,
            'raw_text': text,
            'type': self._detect_transaction_type(text)[0]
        }

        return {
            'amount': amount,
            'category': category,
            'description': description,
            'confidence': confidence,
            'method': 'rule_based',
            'matched_keywords': matched_keywords,
            'raw_text': text,
            'type': self._detect_transaction_type(text)[0]
        }

    def _extract_amount_improved(self, text: str) -> Tuple[Optional[float], float]:
        """
        Improved amount extraction with currency symbol support

        Fixes: "spent $50" now works
        """
        # Try currency symbols first ($50, €50, etc.)
        currency_match = self.currency_pattern.search(text)
        if currency_match:
            try:
                amount = float(currency_match.group(1).replace(',', '.'))
                return amount, 0.95
            except ValueError:
                pass

        # Try regular pattern
        match = self.amount_pattern.search(text)

        if match:
            amount_str = match.group(1).replace(',', '.')
            try:
                amount = float(amount_str)
            except ValueError:
                return None, 0.0

            # Check for multiplier (k, thousand, etc.)
            match_text = match.group(0).lower()
            if any(x in match_text for x in ['k', 'к', 'thousand', 'тысяч', 'т', 'thous']):
                amount *= 1000

            # High confidence for clear numbers >= 10
            confidence = 0.95 if amount >= 10 else 0.85
            return amount, confidence

        return None, 0.0

    def _detect_category_strict(
            self,
            text: str,
            user_categories: Optional[List] = None
    ) -> Tuple[Optional[str], float, List[str]]:
        """
        Strict category detection with FIXED scoring

        Returns: (category_name, confidence, matched_keywords)
        """
        scores = {}
        matched_keywords_map = {}

        # Score default categories
        for category, data in self.category_keywords.items():
            score = 0.0
            matched = []

            # Primary keywords (strong match)
            for keyword in data['primary']:
                if keyword in text:
                    score += 1.0 * data['weight']
                    matched.append(keyword)

            # Secondary keywords (weaker match)
            for keyword in data.get('secondary', []):
                if keyword in text:
                    score += 0.5 * data['weight']
                    matched.append(f"{keyword}*")

            if score > 0:
                scores[category] = score
                matched_keywords_map[category] = matched

        # Check user's custom categories (HIGHEST priority)
        if user_categories:
            for cat in user_categories:
                cat_name_lower = cat.name.lower()

                # Exact match of full category name
                if cat_name_lower in text:
                    return cat.name, 0.95, [cat_name_lower]

                # Check individual words in category name
                cat_words = [w for w in cat_name_lower.split() if len(w) > 3]
                for word in cat_words:
                    if word in text:
                        if cat.name not in scores or scores[cat.name] < 2.5:
                            scores[cat.name] = 2.5
                            matched_keywords_map[cat.name] = [word]

        # Get best match
        if scores:
            best_category = max(scores.items(), key=lambda x: x[1])
            category_name = best_category[0]
            raw_score = best_category[1]

            # FIXED: More generous confidence for clear matches
            if raw_score >= 3.0:  # Very strong (multiple keywords)
                confidence = 0.95
            elif raw_score >= 2.0:  # Strong (primary + secondary or custom)
                confidence = 0.85
            elif raw_score >= 1.5:  # Good (one strong keyword)
                confidence = 0.75
            elif raw_score >= 1.0:  # Acceptable
                confidence = 0.65
            else:  # Weak
                confidence = 0.45

            return category_name, confidence, matched_keywords_map[category_name]

        return None, 0.0, []

    def _calculate_confidence_fixed(
            self,
            amount: Optional[float],
            amount_confidence: float,
            category: Optional[str],
            category_confidence: float,
            matched_keyword_count: int,
            text: str
    ) -> float:
        """
        FIXED confidence calculation (resolves test failures)

        Target:
        - "50k taxi" should be >= 0.85 (high confidence)
        - "50k" should be 0.3-0.85 (medium confidence)
        - "spent on taxi" should be 0.3-0.85 (medium confidence)
        """
        if not amount and not category:
            return 0.1

        if not amount:
            # Has category but no amount - medium confidence
            return max(0.3, category_confidence * 0.6)

        if not category:
            # Has amount but no category - medium confidence
            return max(0.3, amount_confidence * 0.6)

        # Has both - calculate weighted average
        base_confidence = (amount_confidence * 0.5 + category_confidence * 0.5)

        # Boost for multiple keyword matches
        if matched_keyword_count >= 2:
            base_confidence = min(0.98, base_confidence * 1.1)

        # Boost for short, clear messages (less ambiguity)
        word_count = len(text.split())
        if word_count <= 4 and matched_keyword_count >= 1:
            base_confidence = min(0.95, base_confidence * 1.05)

        return round(base_confidence, 3)

    def _should_use_ai(self, result: Dict, text: str) -> bool:
        """
        Decide if AI should be used

        More conservative - only use AI when really needed
        """
        # Very low confidence - use AI
        if result['confidence'] < 0.5:
            return True

        # Has amount but no category - use AI
        if result['amount'] and not result['category']:
            return True

        # Detect potential typos/gibberish
        words = text.lower().split()
        # Simple heuristic: check for very short or very long words
        suspicious = sum(1 for w in words if len(w) > 15 or (len(w) < 3 and w not in ['i', 'on', 'at', 'to', 'k']))

        if suspicious > len(words) * 0.4:  # >40% suspicious
            return True

        # Complex structure (many words without clear pattern)
        if len(words) > 8 and result['confidence'] < 0.75:
            return True

        return False

    def _extract_description(self, text: str, amount: Optional[float]) -> str:
        """Extract clean description"""
        # Remove amount patterns
        if amount:
            text = self.amount_pattern.sub(' ', text)
            text = self.currency_pattern.sub(' ', text)

        # Remove common indicators
        for category_data in self.category_keywords.values():
            for keyword in category_data.get('primary', []) + category_data.get('secondary', []):
                if len(keyword) <= 3:  # Skip short words
                    continue
                text = re.sub(rf'\b{re.escape(keyword)}\b', '', text, flags=re.IGNORECASE)

        # Remove expense indicators
        for indicator in self.expense_indicators['strong'] + self.expense_indicators['weak']:
            text = re.sub(rf'\b{re.escape(indicator)}\b', '', text, flags=re.IGNORECASE)

        # Clean up
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'^(for|on|at|in)\s+', '', text, flags=re.IGNORECASE)

        # Remove special characters at start/end
        text = text.strip('!,.:;-')

        # Limit length
        if len(text) > 100:
            text = text[:97] + '...'

        return text if text else "Transaction"