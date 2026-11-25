# Exercise 1: a broken Kubernetes app

A small shop runs on a local k3d cluster: an `api` (podinfo) behind an nginx `frontend`, locked down with network policies, and watched by Falco. Nothing works quite as intended. Find out why, with `kubectl`, `k9s`, `sofka` and the agent (`omp`, which can talk to the cluster through its Kubernetes MCP server).

The cluster runs on your own machine, next to the dev container. The dev container only gets the cluster's kubeconfig, so the agent can change the cluster but nothing else on your machine.

## 1. Prepare Podman for k3d (once, on your machine)

k3d runs Kubernetes inside rootless Podman, and k3s needs the `cpuset` cgroup, which Podman does not hand out by default. Give the Podman VM at least 4 GB (`podman machine set --memory 4096` while it is stopped).

### macOS

```bash
brew install k3d
podman machine ssh "sudo mkdir -p /etc/systemd/system/user@.service.d && printf '[Service]\nDelegate=cpu cpuset io memory pids\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf"
podman machine stop && podman machine start
export DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')"
```

### Linux

```bash
curl -fsSLo ~/.local/bin/k3d https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-linux-amd64   # or -arm64
chmod +x ~/.local/bin/k3d
sudo mkdir -p /etc/systemd/system/user@.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf
sudo systemctl daemon-reload        # then log out and in again
systemctl --user enable --now podman.socket
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
```

### Windows (PowerShell)

```powershell
winget install k3d.k3d
podman machine ssh "sudo mkdir -p /etc/systemd/system/user@.service.d && printf '[Service]\nDelegate=cpu cpuset io memory pids\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf"
podman machine stop; podman machine start
$env:DOCKER_HOST = "npipe:////./pipe/podman-machine-default"
```

Check: `podman info --format '{{.Host.CgroupControllers}}'` must list `cpuset`.

## 2. Create the cluster (on your machine)

You need this repository on your machine as well, not only in the dev container: clone or download it, then from its `01-kubernetes` folder:

```bash
k3d cluster create --config cluster/k3d.yaml
k3d kubeconfig get workshop
```

Copy the kubeconfig that the second command prints.

## 3. Connect the dev container

In the dev container terminal:

```bash
set-kubeconfig        # paste the kubeconfig, then press Ctrl+D
kubectl get nodes
```

## 4. Deploy and watch it break

```bash
kubectl apply -f falco/
kubectl apply -f app/
k9s                   # or: sofka
```

Then try the shop:

```bash
kubectl -n shop port-forward svc/frontend 8080:80 &
curl -i http://127.0.0.1:8080/
```

You should get the podinfo JSON. You get an error instead.

## 5. Your tasks

1. **Make the shop work.** `curl http://127.0.0.1:8080/` through the frontend must return the podinfo JSON, and every network policy must stay in place: fix them, don't delete them. There is more than one problem.
2. **Make the Falco rule fire.** The rule in `falco/workshop-rules.yaml` should raise a warning whenever someone runs `kubectl exec` in a pod in the `shop` namespace. Try it:
   ```bash
   kubectl -n shop exec deploy/api -- ls /
   kubectl -n falco logs deploy/falco | grep "exec into shop pod"
   ```
   Nothing appears. After changing the rule, apply it and restart Falco with `kubectl -n falco rollout restart deploy/falco`.

Work with the agent: ask it to look at the cluster first and explain what it sees before it changes anything. Compare what it finds with what you see in k9s or sofka.

## Clean up

```bash
k3d cluster delete workshop     # on your machine
```
