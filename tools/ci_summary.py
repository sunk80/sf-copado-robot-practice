"""Print a short Markdown summary of a Robot Framework output.xml (for GitHub job summaries)."""
import os
import sys

from robot.api import ExecutionResult


def main(path: str) -> None:
    if not os.path.exists(path):
        print(f"No results found at `{path}` (the run probably stopped before tests started).")
        return
    result = ExecutionResult(path)
    total = result.statistics.total
    print(f"### {result.suite.name}: {total.passed} passed, {total.failed} failed, {total.skipped} skipped\n")
    failed = [t for t in result.suite.all_tests if t.status == "FAIL"]
    if failed:
        print("| Failed test | Message |\n|---|---|")
        for test in failed:
            message = test.message.replace("\n", " ").replace("|", "\\|")[:300]
            print(f"| {test.longname} | {message} |")
    print("\nDownload the results artifact for log.html, report.html and any CSV reports.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/output.xml")
