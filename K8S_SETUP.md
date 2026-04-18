# Kubernetes Setup

PikaTunnel can manage `Ingress` resources (per proxy route) and keep a LoadBalancer `Service`'s ports in sync with configured routes. When running in-cluster, the pod needs RBAC to do this.

Replace `<namespace>` with the namespace PikaTunnel runs in (and manages resources in). If you manage resources in a different namespace from where PikaTunnel runs, change the `RoleBinding.subjects[0].namespace` to the pod's namespace and keep the `Role`/`RoleBinding` in the target namespace.

## Required permissions

| Resource | API group | Verbs | Why |
| --- | --- | --- | --- |
| `services` | `""` (core) | `get`, `update` | Sync LoadBalancer service ports from routes |
| `ingresses` | `networking.k8s.io` | `get`, `list`, `create`, `update`, `patch`, `delete` | Manage per-route ingresses |

## ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pikatunnel
  namespace: <namespace>
```

## Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pikatunnel
  namespace: <namespace>
rules:
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["get", "update"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "list", "create", "update", "patch", "delete"]
```

## RoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pikatunnel
  namespace: <namespace>
subjects:
  - kind: ServiceAccount
    name: pikatunnel
    namespace: <namespace>
roleRef:
  kind: Role
  name: pikatunnel
  apiGroup: rbac.authorization.k8s.io
```

## All-in-one

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pikatunnel
  namespace: <namespace>
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pikatunnel
  namespace: <namespace>
rules:
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["get", "update"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "list", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pikatunnel
  namespace: <namespace>
subjects:
  - kind: ServiceAccount
    name: pikatunnel
    namespace: <namespace>
roleRef:
  kind: Role
  name: pikatunnel
  apiGroup: rbac.authorization.k8s.io
```

## Using the ServiceAccount

Set `serviceAccountName: pikatunnel` on the PikaTunnel pod spec, then enable in-cluster mode in **Cluster Settings** (or set `k8s_in_cluster=true`). No token/CA is needed when running in-cluster.

## Out-of-cluster token

If PikaTunnel runs outside the cluster, create the same `ServiceAccount` / `Role` / `RoleBinding`, then generate a long-lived token:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: pikatunnel-token
  namespace: <namespace>
  annotations:
    kubernetes.io/service-account.name: pikatunnel
type: kubernetes.io/service-account-token
```

```bash
kubectl -n <namespace> get secret pikatunnel-token -o jsonpath='{.data.token}' | base64 -d
kubectl -n <namespace> get secret pikatunnel-token -o jsonpath='{.data.ca\.crt}' | base64 -d
```

Paste the token and CA cert into **Cluster Settings** along with the API server URL.
