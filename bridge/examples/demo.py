from __future__ import annotations

from harness.agent import Agent
from harness.context import ProjectContext
from harness.llm import MockLLM, draw_square_response


def main() -> None:
    context = ProjectContext.demo()
    agent = Agent(MockLLM([draw_square_response()]), context)
    result = agent.handle("Make the cat draw a square when I click the green flag.", request_id=1)
    print("CHAT SUMMARY")
    print("=" * 60)
    print(result.compiled.chat_summary())
    print()
    print("APPLY LITERAL")
    print("=" * 60)
    print(result.apply_literal)
    print()
    print("CHANGES")
    print("=" * 60)
    for change in result.compiled.changes:
        print(change)


if __name__ == "__main__":
    main()
