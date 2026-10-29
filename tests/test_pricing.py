import pytest

from name2smiles.llm import MODELS, Usage, load_pricing


def test_all_registered_models_have_prices():
    pricing = load_pricing()

    assert set(pricing.models) == set(MODELS)
    assert all(price.currency == "CNY" for price in pricing.models.values())


def test_domestic_prices_are_recorded():
    pricing = load_pricing()

    expected = {
        "deepseek-v4-pro": (4.5, 13.5, 0.15),
        "deepseek-flash": (1.0, 4.0, 0.02),
        "glm-5.3": (8.0, 28.0, 2.0),
        "glm-5.3-flash": (0.8, 2.8, 0.23),
        "minimax-m3.1-flash": (1.0, 4.0, 0.1),
        "longcat-2.5-preview": (2.0, 8.0, 0.04),
        "mimo-v2.6-flash": (1.0, 2.0, 0.02),
        "mimo-v2.6-pro": (3.0, 6.0, 0.025),
        "kimi-k2.6": (6.5, 27.0, 1.1),
        "kimi-k3.1-pro": (13.0, 68.0, 1.3),
        "qwen3.8-flash": (0.8, 2.7, 0.1),
        "qwen3.8-max": (12.0, 36.0, 1.5),
    }
    for key, (input_price, output_price, cache_read) in expected.items():
        price = pricing.price(key)
        assert price.input_per_1m == input_price, key
        assert price.output_per_1m == output_price, key
        assert price.cache_read_per_1m == cache_read, key
        assert price.input_includes_cache is True, key


def test_model_id_alias_resolves_price():
    pricing = load_pricing()

    assert pricing.price("MiniMax-M3.1-Flash").model_key == "minimax-m3.1-flash"



def test_four_router_prices_are_recorded():
    pricing = load_pricing()

    gpt = pricing.price("gpt-6-astra")
    assert gpt.currency == "CNY"
    assert gpt.input_per_1m == 5.0
    assert gpt.output_per_1m == 25.0
    assert gpt.cache_read_per_1m == 0.5
    assert gpt.cache_write_per_1m == 6.25
    assert gpt.input_includes_cache is True

    claude = pricing.price("claude-opus-5.5")
    assert claude.input_per_1m == 6.6
    assert claude.output_per_1m == 33.0
    assert claude.cache_write_per_1m == 8.25
    assert claude.input_includes_cache is False

    gemini = pricing.price("gemini-3.8-flash")
    assert gemini.input_per_1m == 1.5
    assert gemini.output_per_1m == 7.5
    assert gemini.cache_read_per_1m == 0.15


def test_openai_cost_uses_cached_input_subset():
    pricing = load_pricing()
    usage = Usage(
        input_tokens=1_000_000,
        cached_input_tokens=200_000,
        output_tokens=1_000_000,
    )

    estimate = pricing.estimate("gpt-6-astra", usage)

    assert estimate.uncached_input_tokens == 800_000
    assert estimate.cached_input_tokens == 200_000
    assert estimate.input_cost == 4.0
    assert estimate.cache_read_cost == 0.1
    assert estimate.cache_write_cost == 0.0
    assert estimate.output_cost == 25.0
    assert estimate.total_cost == 29.1


def test_anthropic_cost_counts_cache_separately():
    pricing = load_pricing()
    usage = Usage(
        input_tokens=800_000,
        cached_input_tokens=200_000,
        cache_write_input_tokens=100_000,
        output_tokens=1_000_000,
    )

    estimate = pricing.estimate("claude-opus-5.5", usage)

    assert estimate.uncached_input_tokens == 800_000
    assert estimate.input_cost == 5.28
    assert estimate.cache_read_cost == 0.066
    assert estimate.cache_write_cost == 0.825
    assert estimate.output_cost == 33.0
    assert estimate.total_cost == 39.171


def test_anthropic_input_tokens_are_not_reduced_by_cache():
    pricing = load_pricing()
    usage = Usage(
        input_tokens=1_000_000,
        cached_input_tokens=1_000_000,
        output_tokens=0,
    )

    estimate = pricing.estimate("claude-opus-5.5", usage)

    assert estimate.input_cost == 6.6
    assert estimate.cache_read_cost == 0.33


def test_missing_cache_write_price_falls_back_to_input_rate():
    pricing = load_pricing()
    usage = Usage(
        input_tokens=1_000_000,
        cache_write_input_tokens=1_000_000,
        output_tokens=0,
    )

    estimate = pricing.estimate("gemini-4-argon", usage)

    assert estimate.input_cost == 4.0
    assert estimate.cache_write_cost == 4.0
    assert estimate.total_cost == 8.0


def test_unknown_model_has_no_price():
    pricing = load_pricing()

    with pytest.raises(KeyError):
        pricing.price("not-a-real-model")
