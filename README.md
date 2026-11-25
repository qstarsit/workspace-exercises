# Workshop exercises

Three exercises for working with a coding agent (`omp`) in the workshop dev container. Set up the dev container first (see the Agent repository), then clone this repository inside it:

```bash
git clone <this repository> /workspace/exercises
cd /workspace/exercises
```

| Folder | What you do |
|---|---|
| [`01-kubernetes`](01-kubernetes/) | Debug a broken app on a local k3d cluster: network policies, ports and a Falco rule, using kubectl, k9s, sofka and the agent's Kubernetes tools. |
| [`03-fastapi-feature`](03-fastapi-feature/) | Add missing features to a clean FastAPI app that reads flight prices from Hermes, until the tests pass. |

Each folder has its own README with the steps. Exercise 1 also needs a cluster on your own machine; its README explains how.

Let the agent explain the code or cluster before it changes anything, and check what it claims.
