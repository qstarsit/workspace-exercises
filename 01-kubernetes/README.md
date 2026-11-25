# Exercise 1: a broken Kubernetes app

A small shop runs on a local k3d cluster: an `api` (podinfo) behind an nginx `frontend`, locked down with network policies and watched by Falco. It does not work. Make it work, using `kubectl`, `k9s`, `sofka` and your agent (`omp`, which reaches the cluster through its Kubernetes MCP server).

## Setup

### 1. Prepare Podman for k3d (once, on your machine)

Give the Podman VM at least 4 GB (`podman machine set --memory 4096` while it is stopped).

#### macOS

```bash
brew install k3d
podman machine ssh "sudo mkdir -p /etc/systemd/system/user@.service.d && printf '[Service]\nDelegate=cpu cpuset io memory pids\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf"
podman machine stop && podman machine start
export DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')"
```

#### Linux

```bash
curl -fsSLo ~/.local/bin/k3d https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-linux-amd64   # or -arm64
chmod +x ~/.local/bin/k3d
sudo mkdir -p /etc/systemd/system/user@.service.d
printf '[Service]\nDelegate=cpu cpuset io memory pids\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf
sudo systemctl daemon-reload        # then log out and in again
systemctl --user enable --now podman.socket
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
```

#### Windows (PowerShell)

```powershell
winget install k3d.k3d
podman machine ssh "sudo mkdir -p /etc/systemd/system/user@.service.d && printf '[Service]\nDelegate=cpu cpuset io memory pids\n' | sudo tee /etc/systemd/system/user@.service.d/delegate.conf"
podman machine stop; podman machine start
$env:DOCKER_HOST = "npipe:////./pipe/podman-machine-default"
```

Check: `podman info --format '{{.Host.CgroupControllers}}'` lists `cpuset`.

### 2. Create the cluster (on your machine)

From the `01-kubernetes` folder of a local clone of this repository:

```bash
k3d cluster create --config cluster/k3d.yaml
k3d kubeconfig get workshop
```

Copy the kubeconfig that the second command prints.

### 3. Connect the dev container and deploy

In the dev container terminal:

```bash
set-kubeconfig        # paste the kubeconfig, then press Ctrl+D
kubectl get nodes     # check: 1 node, Ready
kubectl apply -f falco/
kubectl apply -f app/
kubectl -n shop port-forward svc/frontend 8080:80 &
```

## Tasks

1. **Make the shop work.**
   Don't delete a NetworkPolicy or make one allow-all. Done when `curl -i http://127.0.0.1:8080/` returns HTTP 200 with the podinfo JSON.

2. **Make the Falco rule fire.** The rule `Shell into shop pod` must raise a warning whenever someone runs `kubectl exec` in a pod in the `shop` namespace.
   Apply changes with:
   ```bash
   kubectl apply -f falco/
   kubectl -n falco rollout restart deploy/falco
   ```
   Done when, after `kubectl -n shop exec deploy/api -- ls /`, the command `kubectl -n falco logs deploy/falco | grep "exec into shop pod"` prints a line.

## Clean up

```bash
k3d cluster delete workshop     # on your machine
```
