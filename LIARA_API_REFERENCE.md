# 📚 Liara PaaS API Reference - برای SRE Agent

> **Base URL**: `https://api.liara.ir`
> **Auth**: `Authorization: Bearer YOUR_API_TOKEN` (JWT Bearer Token from Console)
> **WebSocket**: `wss://api.liara.ir?token=<api-token>&cmd=/bin/bash&project_id=<project-id>`

---

## 🔐 Authentication
```typescript
Authorization: Bearer liara_xxxxxxxxxxxxxxxx
```

---

## 📦 Apps (Projects) Management

### List All Projects
```http
GET /v1/projects
```
**Response**: `Projects[]` with `_id`, `project_id`, `type`, `status`, `scale`, `planID`, `created_at`, `isDeployed`

### Get Project Details
```http
GET /v1/projects/{name}
```

### Create New Project
```http
POST /v1/projects
{ "name": "my-app", "planID": "small", "platform": "nodejs", "readOnlyRootFilesystem": false, "network": "default" }
```
**Platforms**: `nodejs`, `python`, `go`, `php`, `ruby`, `dotnet`, `static`, `docker`, `java`, `rust`, `deno`, `bun`

### Delete Project
```http
DELETE /v1/projects/{name}
```

### Restart App
```http
POST /v1/projects/{name}/actions/restart
```

### Scale (Turn On/Off)
```http
POST /v1/projects/{name}/actions/scale
{ "scale": 1 }  // 1 = on, 0 = off
```

### Change Plan (Resize)
```http
POST /v1/projects/{name}/resize
{ "planID": "medium" }
```

### Zero-Downtime Deployment
```http
POST /v1/projects/{id}/zero-downtime/{status}  // status: "enable" | "disable"
```---

## 🚀 Deployments

### Deploy Source Code (v2)
`http
POST /v2/projects/{name}/sources
Content-Type: multipart/form-data
file: <application.tar.gz>  // required: .gz compressed source code
`
**Response**: { "sourceID": "src_xxxxx" }

### Deploy Release (Docker Image / Source)
`http
POST /v2/projects/{name}/releases
{ "sourceID": "src_xxxxx", "port": 3000, "type": "nodejs" }
`
**Response**: { "releaseID": "rel_xxxxx" }

### Get Releases (Paginated)
`http
GET /v1/projects/{name}/releases?page=1&count=10
`

### Get Deployment Events
`http
GET /v1/projects/{name}/events?search=deploy&start=1704028315&end=1704114715
`

---

## 📊 Metrics & Monitoring (Reports)
`http
GET /v1/projects/{name}/reports
`
**Query Params**: metric (cpu|memory|network|disk), period (1h|6h|24h|7d|30d), ggregation (avg|max|min|p50|p95|p99)

---

## 📝 Logs

### Get Application Logs
`http
GET /v1/projects/{name}/logs?since=1704028315
`
**Required**: since (Unix timestamp)

### Real-time Streaming (WebSocket)
`
wss://api.liara.ir?token=<api-token>&cmd=/bin/bash&project_id=<project-id>
`

---

## ⚙️ Environment Variables
`http
POST /v1/projects/update-envs
{ "project": "my-app", "variables": [{ "key": "NODE_ENV", "value": "production" }] }
`

---

## 🌐 Domains
`http
GET /v1/domains?project=my-app
POST /v1/domains { "name": "example.com", "type": "primary" }
POST /v1/domains/set-project { "domainID": "dom_xxxxx", "projectID": "my-app" }
`

---

## 💾 Disks (Persistent Storage)
`http
GET /v1/projects/{name}/disks
POST /v1/projects/{name}/disks { "name": "data", "size": 10 }
POST /v1/projects/{name}/disks/{diskID}/resize { "size": 20 }
POST /v1/projects/{name}/disks/{diskID}/backups
GET /v1/projects/{name}/disks/{diskID}/backups
GET /v1/projects/{name}/disks/{diskID}/backups/{backupID}/download
`

---

## 🏷️ Plans (Pricing Tiers)
> Plans not directly exposed via API. Referenced by planID: micro, small, medium, large, xlarge, xxlarge
> Maintain local mapping table with CPU/RAM/Disk/Bandwidth/Price (IRR/month).

---

## 🔧 Settings
`http
GET /v1/projects/{name}/settings/default-subdomain
POST /v1/projects/{name}/settings/ip-static
POST /v1/projects/{name}/settings/read-only { "enabled": true }
`

---

## 🔗 Git Integration
`http
GET /v1/user/git-integrations
`

---

## 👤 User & Billing
`http
GET /v1/me
GET /v1/billing
GET /v1/user/free-credit
`

---

## 📋 Error Responses
| Code | Meaning |
|------|---------|
| 400 | Validation error |
| 401 | Missing authentication |
| 404 | App does not exist |
| 409 | Conflict |
| 429 | Rate limit exceeded |

---

## ⚡ Rate Limits
Not explicitly documented. Implement exponential backoff, cache responses, respect Retry-After header.
**Recommended**: 60 req/min read, 20 req/min write.

---

## 🎯 SRE Agent - Required Endpoints Mapping

| Feature | Endpoints | Priority |
|---------|-----------|----------|
| Project Analysis | GET /v1/projects, GET /v1/projects/{name} | 🔴 Critical |
| Plan Recommendation | Local mapping + POST /v1/projects | 🔴 Critical |
| Deploy (Source) | POST /v2/projects/{name}/sources, POST /v2/projects/{name}/releases | 🔴 Critical |
| Deploy (Docker) | POST /v2/projects/{name}/releases | 🟡 High |
| Deploy Logs (Live) | WebSocket wss://api.liara.ir | 🔴 Critical |
| Deployment Status | GET /v1/projects/{name}/releases, GET /v1/projects/{name}/events | 🔴 Critical |
| Restart | POST /v1/projects/{name}/actions/restart | 🔴 Critical |
| Scale On/Off | POST /v1/projects/{name}/actions/scale | 🟡 High |
| Change Plan | POST /v1/projects/{name}/resize | 🟡 High |
| Environment Variables | POST /v1/projects/update-envs | 🔴 Critical |
| Domains + SSL | GET/POST /v1/domains, POST /v1/domains/set-project | 🟡 High |
| Metrics | GET /v1/projects/{name}/reports | 🔴 Critical |
| Logs (Historical) | GET /v1/projects/{name}/logs?since=... | 🔴 Critical |
| Logs (Live) | WebSocket | 🟡 High |
| Disks & Backups | GET/POST /v1/projects/{name}/disks/* | 🟢 Medium |
| Rollback | Deploy previous eleaseID via releases endpoint | 🟡 High |
| Zero-Downtime | POST /v1/projects/{name}/zero-downtime/enable | 🟢 Medium |

---

## 🚫 Known Limitations (Must Communicate to User)

1. **No Real-time Metrics Push** - Polling required for live metrics
2. **No Native Alerting API** - Must implement threshold checking client-side
3. **No Webhook for Deploy Events** - Poll /events every 30s or use GitHub webhooks
4. **Logs Since Timestamp Only** - No tail/follow via REST (WebSocket only)
5. **Plan Details Not via API** - Must maintain local plan catalog
6. **No Direct Container Shell** - WebSocket provides bash access only
7. **Rate Limits Undocumented** - Conservative client-side throttling needed
8. **No Team/Project Permissions API** - Limited to token owner's resources

---

## 💡 TypeScript Client Skeleton

`	ypescript
// packages/liara-api/src/client.ts
export class LiaraClient {
  private baseUrl = 'https://api.liara.ir';
  constructor(private token: string) {}
  
  private async request<T>(method: string, path: string, body?: any): Promise<T> {
    const res = await fetch(${this.baseUrl}, {
      method,
      headers: {
        'Authorization': Bearer ,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    
    if (res.status === 429) {
      const retryAfter = res.headers.get('Retry-After') || '60';
      throw new RateLimitError(parseInt(retryAfter));
    }
    
    if (!res.ok) {
      throw new LiaraApiError(res.status, await res.text());
    }
    
    return res.status === 204 ? undefined as any : res.json();
  }
  
  // Apps
  getProjects() { return this.request('GET', '/v1/projects'); }
  getProject(name: string) { return this.request('GET', /v1/projects/); }
  createProject(data: any) { return this.request('POST', '/v1/projects', data); }
  deleteProject(name: string) { return this.request('DELETE', /v1/projects/); }
  restartProject(name: string) { return this.request('POST', /v1/projects//actions/restart); }
  scaleProject(name: string, scale: 0 | 1) { return this.request('POST', /v1/projects//actions/scale, { scale }); }
  changePlan(name: string, planID: string) { return this.request('POST', /v1/projects//resize, { planID }); }
  setZeroDowntime(name: string, enabled: boolean) { return this.request('POST', /v1/projects//zero-downtime/); }
  
  // Deploy
  deployRelease(name: string, data: any) { return this.request('POST', /v2/projects//releases, data); }
  getReleases(name: string, page = 1, count = 10) { return this.request('GET', /v1/projects//releases?page=&count=); }
  
  // Monitoring
  getLogs(name: string, since: number) { return this.request('GET', /v1/projects//logs?since=); }
  
  // Env
  updateEnvs(project: string, variables: any[]) { return this.request('POST', '/v1/projects/update-envs', { project, variables }); }
  
  // Domains
  getDomains(project: string) { return this.request('GET', /v1/domains?project=); }
  createDomain(name: string) { return this.request('POST', '/v1/domains', { name }); }
  attachDomain(domainID: string, projectID: string) { return this.request('POST', '/v1/domains/set-project', { domainID, projectID }); }
  
  // User
  getUser() { return this.request('GET', '/v1/me'); }
  getBilling() { return this.request('GET', '/v1/billing'); }
}
`

---

## 🔗 Useful Links
- **API Docs**: https://developers.liara.ir/
- **OpenAPI Spec**: https://developers.liara.ir/spec/paas.yaml
- **LLMS Index**: https://developers.liara.ir/llms.txt
- **Console (Get Token)**: https://console.liara.ir/
- **Support**: support@liara.ir
- **GitHub**: https://github.com/liara-cloud
