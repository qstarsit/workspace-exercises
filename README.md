# Workshop exercises

Exercises for working with a coding agent (`omp`) in the workshop dev container. Set up the dev container first (see the Agent repository), then clone this repository inside it:

```bash
git clone <this repository> /workspace/exercises
cd /workspace/exercises
```

| Folder | What you do |
|---|---|
| [`01-kubernetes`](01-kubernetes/) | Get a broken shop running on a local k3d cluster without weakening its security, using kubectl, k9s, sofka and the agent's Kubernetes tools. |
| [`02-fastapi-feature`](02-fastapi-feature/) | Add missing features to a FastAPI app on the Hermes flight-price API until the tests pass. |
| [`03-finetuning`](03-finetuning/) | Fine-tune a 135M model on your CPU to replace GLM-5 for one task. |
| [`04-build-an-agent`](04-build-an-agent/) | Give a minimal agent tools to search, test and edit code, then let it fix a failing test. |

Each folder has its own README. Let the agent explain the code or cluster before it changes anything, and check what it claims.
