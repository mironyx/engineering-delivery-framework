"""Extract a project item ID from a GraphQL response on stdin.

Usage: parse-project-item-id.py <project_id>

Reads the GraphQL response for issue.projectItems from stdin, finds the
node whose project.id matches <project_id>, and prints its node.id.
Exits 0 if found, 1 if not found.
"""

import json
import sys


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: parse-project-item-id.py <project_id>\n")
        sys.exit(1)

    target_project_id = sys.argv[1]
    data = json.load(sys.stdin)
    nodes = data["data"]["repository"]["issue"]["projectItems"]["nodes"]

    for node in nodes:
        if node["project"]["id"] == target_project_id:
            print(node["id"])
            sys.exit(0)

    print("")
    sys.exit(1)


if __name__ == "__main__":
    main()
