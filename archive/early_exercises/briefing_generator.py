"""Generate a weekly UK economic news briefing using Claude with web search."""

import sys
from datetime import date
from pathlib import Path

import anthropic

MODEL = "claude-opus-4-8"
PROMPT = (
    "Summarise this week's most important UK economic news in under 300 words, "
    "covering inflation, interest rates, and one major news item. Cite your sources."
)


def generate_briefing() -> str:
    client = anthropic.Anthropic()

    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{"role": "user", "content": PROMPT}],
    ) as stream:
        response = stream.get_final_message()

    # Web search citations split the answer into multiple adjacent text
    # blocks; concatenate with no separator to reconstruct the prose.
    return "".join(block.text for block in response.content if block.type == "text")


def main() -> None:
    briefing = generate_briefing()
    print(briefing)

    today = date.today().isoformat()
    output_path = Path(f"uk_economic_briefing_{today}.md")
    output_path.write_text(
        f"# UK Economic Briefing — {today}\n\n{briefing}\n",
        encoding="utf-8",
    )
    print(f"\nSaved to {output_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        print("Invalid or missing ANTHROPIC_API_KEY.", file=sys.stderr)
        sys.exit(1)
    except anthropic.RateLimitError:
        print("Rate limited by the Anthropic API. Try again shortly.", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"API error {e.status_code}: {e.message}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("Network error connecting to the Anthropic API.", file=sys.stderr)
        sys.exit(1)
