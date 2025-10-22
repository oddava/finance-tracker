"""
Comprehensive tests for ExpenseParser
"""
import asyncio
import time
import pytest
from bot.services.expense_parser import ExpenseParser


# Mock category class
class MockCategory:
    def __init__(self, name: str):
        self.name = name


@pytest.fixture
def parser():
    """Create parser instance"""
    return ExpenseParser(openai_api_key=None)  # No AI for basic tests


@pytest.fixture
def sample_categories():
    """Sample user categories"""
    return [
        MockCategory("Food & Dining"),
        MockCategory("Transportation"),
        MockCategory("Groceries"),
        MockCategory("Entertainment"),
        MockCategory("Shopping")
    ]


class TestAmountExtraction:
    """Test amount parsing"""

    @pytest.mark.asyncio
    async def test_simple_numbers(self, parser):
        """Test simple number formats"""
        test_cases = [
            ("50000 taxi", 50000),
            ("taxi 50000", 50000),
            ("25000", 25000),
            ("150.5", 150.5),
        ]

        for text, expected in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['amount'] == expected, f"Failed for: {text}"

    @pytest.mark.asyncio
    async def test_k_notation(self, parser):
        """Test 'k' notation"""
        test_cases = [
            ("50k taxi", 50000),
            ("50K taxi", 50000),
            ("50 k taxi", 50000),
            ("50к такси", 50000),  # Cyrillic 'к'
            ("2.5k groceries", 2500),
        ]

        for text, expected in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['amount'] == expected, f"Failed for: {text}"

    @pytest.mark.asyncio
    async def test_decimal_amounts(self, parser):
        """Test decimal number support"""
        test_cases = [
            ("25.50 coffee", 25.5),
            ("100,50 lunch", 100.5),  # Comma as decimal
            ("1.5k taxi", 1500),
        ]

        for text, expected in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['amount'] == expected, f"Failed for: {text}"


class TestCategoryDetection:
    """Test category detection"""

    @pytest.mark.asyncio
    async def test_common_categories(self, parser, sample_categories):
        """Test detection of common categories"""
        test_cases = [
            ("50k taxi", "transport"),
            ("lunch 25000", "food"),
            ("bought groceries 120k", "groceries"),
            ("movie ticket 35k", "entertainment"),
            ("shopping clothes 200k", "shopping"),
            ("electricity bill 150k", "bills"),
        ]

        for text, expected_cat in test_cases:
            result = await parser.parse(text, user_id=1, user_categories=sample_categories)
            assert result['category'] == expected_cat, f"Failed for: {text}, got {result['category']}"

    @pytest.mark.asyncio
    async def test_multilingual(self, parser):
        """Test Russian/Uzbek language support"""
        test_cases = [
            ("такси 50к", "transport"),
            ("обед 25000", "food"),
            ("продукты 120к", "groceries"),
            ("кофе 15к", "food"),
        ]

        for text, expected_cat in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['category'] == expected_cat, f"Failed for: {text}"

    @pytest.mark.asyncio
    async def test_user_categories(self, parser, sample_categories):
        """Test matching against user's custom categories"""
        result = await parser.parse(
            "Food & Dining 50k",
            user_id=1,
            user_categories=sample_categories
        )
        assert result['category'].lower() == "food & dining"
        assert result['confidence'] > 0.8


class TestConfidenceScoring:
    """Test confidence calculation"""

    @pytest.mark.asyncio
    async def test_high_confidence(self, parser):
        """Test cases that should have high confidence"""
        test_cases = [
            "50k taxi",
            "lunch 25000",
            "groceries 120k"
        ]

        for text in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['confidence'] >= 0.85, f"Low confidence for: {text} ({result['confidence']})"

    @pytest.mark.asyncio
    async def test_medium_confidence(self, parser):
        """Test cases with medium confidence"""
        test_cases = [
            "50k",  # Amount but no category
            "spent on taxi",  # Category but no amount
        ]

        for text in test_cases:
            result = await parser.parse(text, user_id=1)
            assert 0.3 <= result['confidence'] < 0.85, f"Wrong confidence for: {text}"

    @pytest.mark.asyncio
    async def test_low_confidence(self, parser):
        """Test ambiguous cases"""
        test_cases = [
            "hello",
            "how are you",
            "spent money"
        ]

        for text in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['confidence'] < 0.5, f"Too high confidence for: {text}"


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_input(self, parser):
        """Test empty string"""
        result = await parser.parse("", user_id=1)
        assert result['amount'] is None
        assert result['confidence'] < 0.2

    @pytest.mark.asyncio
    async def test_very_long_text(self, parser):
        """Test long descriptions"""
        text = "bought some groceries at the market " + "blah " * 50 + "150k"
        result = await parser.parse(text, user_id=1)
        assert result['amount'] == 150000
        assert len(result['description']) <= 100  # Should be truncated

    @pytest.mark.asyncio
    async def test_multiple_amounts(self, parser):
        """Test handling multiple amounts"""
        result = await parser.parse("spent 50k on taxi and 25k on lunch", user_id=1)
        # Should extract the first amount
        assert result['amount'] in [50000, 25000]

    @pytest.mark.asyncio
    async def test_special_characters(self, parser):
        """Test special characters"""
        test_cases = [
            "50k taxi!",
            "lunch - 25000",
            "groceries: 120k",
            "spent $50",
        ]

        for text in test_cases:
            result = await parser.parse(text, user_id=1)
            assert result['amount'] is not None, f"Failed to parse: {text}"


class TestPerformance:
    """Performance benchmarks"""

    @pytest.mark.asyncio
    async def test_parsing_speed(self, parser):
        """Test that rule-based parsing is fast"""
        test_texts = [
                         "50k taxi",
                         "lunch 25000",
                         "groceries 120k",
                         "movie 35k",
                         "shopping 200k"
                     ] * 20  # 100 tests

        start_time = time.time()

        for text in test_texts:
            await parser.parse(text, user_id=1)

        elapsed = time.time() - start_time
        avg_time = elapsed / len(test_texts) * 1000  # ms

        print(f"\nAverage parsing time: {avg_time:.2f}ms")
        assert avg_time < 5, f"Too slow: {avg_time:.2f}ms per parse"

    @pytest.mark.asyncio
    async def test_batch_performance(self, parser, sample_categories):
        """Test batch parsing performance"""
        texts = [
            "50k taxi", "lunch 25000", "groceries 120k",
            "movie ticket 35k", "coffee 15k", "uber 40k",
            "dinner 80k", "market 150k", "gas 200k",
            "netflix 35k"
        ]

        start_time = time.time()

        results = []
        for text in texts * 10:  # 100 parses
            result = await parser.parse(text, user_id=1, user_categories=sample_categories)
            results.append(result)

        elapsed = time.time() - start_time

        print(f"\nBatch processing: {len(results)} items in {elapsed:.2f}s")
        print(f"Average: {elapsed / len(results) * 1000:.2f}ms per item")

        # Should process 100 items in under 1 second
        assert elapsed < 1.0, f"Batch processing too slow: {elapsed:.2f}s"


class TestRealWorldExamples:
    """Test with real-world user inputs"""

    @pytest.mark.asyncio
    async def test_casual_inputs(self, parser):
        """Test natural, casual language"""
        test_cases = [
            ("spent 50 on taxi", 50, "transport"),
            ("bought coffee for 15k", 15000, "food"),
            ("lunch was 25k", 25000, "food"),
            ("paid 120 for groceries", 120, "groceries"),
            ("uber ride 40k", 40000, "transport"),
        ]

        for text, expected_amount, expected_cat in test_cases:
            result = await parser.parse(text, user_id=1)

            # Check amount (allow for 'k' multiplication)
            if result['amount']:
                amount_matches = (
                        result['amount'] == expected_amount or
                        result['amount'] == expected_amount * 1000
                )
                assert amount_matches, f"Amount mismatch for '{text}': got {result['amount']}"

            # Check category
            assert result['category'] == expected_cat, f"Category mismatch for '{text}': got {result['category']}"

    @pytest.mark.asyncio
    async def test_typos_and_variations(self, parser):
        """Test tolerance for typos"""
        test_cases = [
            "50k txi",  # typo in taxi
            "lnch 25k",  # typo in lunch
            "groc 120k",  # abbreviated groceries
        ]

        for text in test_cases:
            result = await parser.parse(text, user_id=1)
            # Should still extract amount even with typos
            assert result['amount'] is not None, f"Failed to parse amount from: {text}"


# Manual benchmark script
async def benchmark():
    """Run manual benchmark"""
    parser = ExpenseParser()

    test_cases = [
        "50k taxi",
        "lunch 25000",
        "spent 150k on groceries",
        "movie ticket 35 thousand",
        "bought coffee 15k",
        "uber ride to airport 80k",
        "dinner at restaurant 120k",
        "monthly internet bill 200k",
        "gas station 250k",
        "shopping for clothes 500k"
    ]

    print("=" * 60)
    print("EXPENSE PARSER BENCHMARK")
    print("=" * 60)

    total_time = 0
    successful = 0
    high_confidence = 0

    for text in test_cases * 10:  # 100 iterations
        start = time.time()
        result = await parser.parse(text, user_id=1)
        elapsed = time.time() - start
        total_time += elapsed

        if result['amount'] and result['category']:
            successful += 1
        if result['confidence'] >= 0.85:
            high_confidence += 1

    total_tests = len(test_cases) * 10
    avg_time = (total_time / total_tests) * 1000

    print(f"\nResults:")
    print(f"  Total tests: {total_tests}")
    print(f"  Successful parses: {successful} ({successful / total_tests * 100:.1f}%)")
    print(f"  High confidence: {high_confidence} ({high_confidence / total_tests * 100:.1f}%)")
    print(f"  Average time: {avg_time:.2f}ms")
    print(f"  Total time: {total_time:.3f}s")
    print(f"\nPerformance: {'✅ EXCELLENT' if avg_time < 1 else '✅ GOOD' if avg_time < 5 else '⚠️  NEEDS OPTIMIZATION'}")
    print("=" * 60)


if __name__ == "__main__":
    # Run benchmark
    asyncio.run(benchmark())